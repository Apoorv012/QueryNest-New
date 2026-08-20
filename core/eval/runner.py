from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExpectedDoc:
    document_filename: str
    relevance: int
    text_contains: str = ""


@dataclass
class EvalQuery:
    id: str
    query: str
    type: str
    expected_docs: list[ExpectedDoc]
    min_relevant: int = 1


@dataclass
class QueryResult:
    query: EvalQuery
    retrieved_doc_ids: list[str]
    retrieved_doc_filenames: list[str]
    precisions: dict[int, float] = field(default_factory=dict)
    recalls: dict[int, float] = field(default_factory=dict)
    ndcg: dict[int, float] = field(default_factory=dict)
    rr: float = 0.0
    latency_ms: float = 0.0


def load_golden(path: Path) -> list[EvalQuery]:
    data = json.loads(path.read_text(encoding="utf-8"))
    queries = []
    for q in data["queries"]:
        expected = [
            ExpectedDoc(
                document_filename=e["document_filename"],
                relevance=e["relevance"],
                text_contains=e.get("text_contains", ""),
            )
            for e in q["expected_docs"]
        ]
        queries.append(EvalQuery(
            id=q["id"],
            query=q["query"],
            type=q["type"],
            expected_docs=expected,
            min_relevant=q.get("min_relevant", 1),
        ))
    return queries


EVAL_USER_ID = "golden_user"


def get_document_filename_map(user_id: str = EVAL_USER_ID) -> dict[str, str]:
    """Map document_id -> normalized filename (no extension) for the eval user.

    Search results only carry the store-assigned `document_id` (a random hex
    id assigned at ingest time, unrelated to the original filename), while
    the golden set identifies expected docs by `document_filename` (e.g.
    "attention_2017"). This bridges the two via GET /documents.
    """
    import requests

    base = os.environ.get("QUERYNEST_API_URL", "http://localhost:8000")
    resp = requests.get(f"{base}/documents", params={"user_id": user_id}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    mapping = {}
    for d in data.get("documents", []):
        filename = d.get("filename", "")
        stem = Path(filename).stem
        mapping[d["document_id"]] = stem
    return mapping


def get_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, timeout=5, check=False,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def run_search(
    query_text: str, top_k: int = 10, user_id: str = EVAL_USER_ID
) -> tuple[list[dict], float]:
    import requests
    base = os.environ.get("QUERYNEST_API_URL", "http://localhost:8000")
    start = time.perf_counter()
    resp = requests.post(
        f"{base}/search",
        json={"query": query_text, "top_k": top_k, "user_id": user_id},
        timeout=30,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    resp.raise_for_status()
    data = resp.json()
    return data.get("results", []), elapsed_ms


def run_eval(
    golden_path: Path, top_k: int = 10, user_id: str = EVAL_USER_ID
) -> list[QueryResult]:
    from core.eval.metrics import mrr, ndcg_at_k, precision_at_k, recall_at_k

    queries = load_golden(golden_path)
    id_to_filename = get_document_filename_map(user_id)
    results = []

    for q in queries:
        raw_results, latency_ms = run_search(q.query, top_k, user_id)

        # Search returns store-assigned document_id; the golden set identifies
        # expected docs by filename stem, so translate before comparing.
        retrieved_doc_ids_raw = [r.get("document_id", "") for r in raw_results]
        retrieved_filenames_raw = [
            id_to_filename.get(doc_id, doc_id) for doc_id in retrieved_doc_ids_raw
        ]

        # Relevance (and the golden set) is judged per document, but a
        # document can surface multiple times via different chunks. Dedupe
        # to document level, preserving rank order (first occurrence wins),
        # before computing any metric — otherwise duplicate hits inflate
        # recall past 1.0 and skew nDCG/MRR.
        retrieved_doc_ids: list[str] = []
        retrieved_filenames: list[str] = []
        seen: set[str] = set()
        for doc_id, filename in zip(retrieved_doc_ids_raw, retrieved_filenames_raw):
            if filename in seen:
                continue
            seen.add(filename)
            retrieved_doc_ids.append(doc_id)
            retrieved_filenames.append(filename)

        relevant_set = {e.document_filename for e in q.expected_docs if e.relevance >= 1}

        pr = QueryResult(
            query=q,
            retrieved_doc_ids=retrieved_doc_ids,
            retrieved_doc_filenames=retrieved_filenames,
            latency_ms=latency_ms,
        )

        for k in [5, 10]:
            pr.precisions[k] = precision_at_k(retrieved_filenames, relevant_set, k)
            pr.recalls[k] = recall_at_k(retrieved_filenames, relevant_set, k)

        relevances = []
        for doc_filename in retrieved_filenames:
            rel = 0
            for e in q.expected_docs:
                if e.document_filename == doc_filename:
                    rel = max(rel, e.relevance)
            relevances.append(rel)
        # The ideal ranking comes from the golden set's own relevance
        # judgments, not from whatever was retrieved — otherwise a
        # well-ordered-but-mediocre result set scores a perfect 1.0.
        # It must be deduped per document (best grade wins) to match the
        # deduped retrieval above: a golden entry listing the same document
        # twice describes two passages, not two retrievable documents, and
        # leaving the duplicate in makes even perfect retrieval score < 1.0.
        best_by_doc: dict[str, int] = {}
        for e in q.expected_docs:
            best_by_doc[e.document_filename] = max(
                best_by_doc.get(e.document_filename, 0), e.relevance
            )
        ideal_relevances = list(best_by_doc.values())
        pr.ndcg[10] = ndcg_at_k(relevances, ideal_relevances, 10)

        pr.rr = mrr(retrieved_filenames, relevant_set)

        results.append(pr)

    return results
