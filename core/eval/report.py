from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .runner import QueryResult, get_git_commit


def _avg(vals: list[float]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _aggregate_metrics(results: list[QueryResult]) -> dict[str, float]:
    """Corpus-wide metric averages for one retriever's results."""
    precisions5 = [r.precisions.get(5, 0) for r in results]
    precisions10 = [r.precisions.get(10, 0) for r in results]
    recalls5 = [r.recalls.get(5, 0) for r in results]
    recalls10 = [r.recalls.get(10, 0) for r in results]
    ndcg10 = [r.ndcg.get(10, 0) for r in results]
    rr = [r.rr for r in results]
    return {
        "precision_at_5": round(_avg(precisions5), 4),
        "precision_at_10": round(_avg(precisions10), 4),
        "recall_at_5": round(_avg(recalls5), 4),
        "recall_at_10": round(_avg(recalls10), 4),
        "ndcg_at_10": round(_avg(ndcg10), 4),
        "mrr": round(_avg(rr), 4),
    }


def generate_report(
    results: list[QueryResult],
    output_dir: Path,
    bm25_results: list[QueryResult] | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    commit = get_git_commit()
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")

    all_latencies = [r.latency_ms for r in results]

    by_type: dict[str, list[QueryResult]] = {}
    for r in results:
        by_type.setdefault(r.query.type, []).append(r)

    report: dict[str, Any] = {
        "timestamp": timestamp,
        "git_commit": commit,
        "total_queries": len(results),
        "metrics": _aggregate_metrics(results),
        "latency_ms_avg": round(_avg(all_latencies), 1),
        "by_type": {},
        "worst_queries": [],
        "query_results": [],
    }

    for qtype, type_results in sorted(by_type.items()):
        report["by_type"][qtype] = {
            "count": len(type_results),
            "precision_at_5": round(_avg([r.precisions.get(5, 0) for r in type_results]), 4),
            "recall_at_10": round(_avg([r.recalls.get(10, 0) for r in type_results]), 4),
        }

    sorted_by_mrr = sorted(results, key=lambda r: r.rr)
    for r in sorted_by_mrr[:5]:
        report["worst_queries"].append({
            "query_id": r.query.id,
            "query": r.query.query,
            "mrr": round(r.rr, 4),
            "precision_at_5": round(r.precisions.get(5, 0), 4),
        })

    for r in results:
        report["query_results"].append({
            "query_id": r.query.id,
            "query": r.query.query,
            "type": r.query.type,
            "precision_at_5": round(r.precisions.get(5, 0), 4),
            "recall_at_10": round(r.recalls.get(10, 0), 4),
            "mrr": round(r.rr, 4),
            "latency_ms": round(r.latency_ms, 1),
        })

    # Phase 1.4: a metric without a baseline is not an achievement. When a
    # BM25 run is supplied, record it alongside semantic under the same
    # metric shape, plus a per-query win/loss breakdown, so the comparison
    # is reproducible from the saved report and not just the console table.
    if bm25_results is not None:
        bm25_by_id = {r.query.id: r for r in bm25_results}
        semantic_wins = 0
        bm25_wins = 0
        ties = 0
        per_query_comparison = []
        for r in results:
            b = bm25_by_id.get(r.query.id)
            if b is None:
                continue
            if r.rr > b.rr:
                semantic_wins += 1
                winner = "semantic"
            elif b.rr > r.rr:
                bm25_wins += 1
                winner = "bm25"
            else:
                ties += 1
                winner = "tie"
            per_query_comparison.append({
                "query_id": r.query.id,
                "query": r.query.query,
                "type": r.query.type,
                "semantic_mrr": round(r.rr, 4),
                "bm25_mrr": round(b.rr, 4),
                "winner": winner,
            })

        report["baselines"] = {
            "bm25": {
                "total_queries": len(bm25_results),
                "metrics": _aggregate_metrics(bm25_results),
                "latency_ms_avg": round(_avg([r.latency_ms for r in bm25_results]), 1),
            },
        }
        report["comparison"] = {
            "semantic_wins": semantic_wins,
            "bm25_wins": bm25_wins,
            "ties": ties,
            "per_query": per_query_comparison,
        }

    filename = f"report_{timestamp}_{commit}.json"
    output_path = output_dir / filename
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return output_path


def print_report(results: list[QueryResult]) -> None:
    all_precisions: dict[int, list[float]] = {5: [], 10: []}
    all_recalls: dict[int, list[float]] = {5: [], 10: []}
    all_ndcg: dict[int, list[float]] = {10: []}
    all_rr: list[float] = []

    by_type: dict[str, list[QueryResult]] = {}
    for r in results:
        by_type.setdefault(r.query.type, []).append(r)
        for k in [5, 10]:
            all_precisions[k].append(r.precisions.get(k, 0))
            all_recalls[k].append(r.recalls.get(k, 0))
        all_ndcg[10].append(r.ndcg.get(10, 0))
        all_rr.append(r.rr)

    def avg(vals: list[float]) -> float:
        return sum(vals) / len(vals) if vals else 0.0

    print(f"\nQueryNest Evaluation Report ({len(results)} queries)")
    print("=" * 50)
    print(f"  Precision@5:  {avg(all_precisions[5]):.4f}")
    print(f"  Precision@10: {avg(all_precisions[10]):.4f}")
    print(f"  Recall@5:     {avg(all_recalls[5]):.4f}")
    print(f"  Recall@10:    {avg(all_recalls[10]):.4f}")
    print(f"  NDCG@10:      {avg(all_ndcg[10]):.4f}")
    print(f"  MRR:          {avg(all_rr):.4f}")

    print("\nBy Query Type:")
    for qtype, type_results in sorted(by_type.items()):
        p5 = avg([r.precisions.get(5, 0) for r in type_results])
        r10 = avg([r.recalls.get(10, 0) for r in type_results])
        print(f"  {qtype:15s} P@5={p5:.2f}  R@10={r10:.2f}  (n={len(type_results)})")

    print("\nWorst Queries:")
    sorted_by_mrr = sorted(results, key=lambda r: r.rr)
    for r in sorted_by_mrr[:5]:
        print(f"  {r.query.id}: \"{r.query.query}\" (MRR={r.rr:.2f}, P@5={r.precisions.get(5, 0):.2f})")


def print_comparison(
    semantic_results: list[QueryResult], bm25_results: list[QueryResult]
) -> None:
    """Side-by-side semantic vs BM25 table (Phase 1.4).

    A metric without a baseline is not an achievement — this is what makes
    the semantic numbers interpretable. BM25 is expected to win some
    queries (exact identifiers, proper nouns); that is a legitimate finding
    about the corpus, not a bug in either retriever.
    """
    sem = _aggregate_metrics(semantic_results)
    bm25 = _aggregate_metrics(bm25_results)

    rows = [
        ("Precision@5", "precision_at_5"),
        ("Recall@5", "recall_at_5"),
        ("Recall@10", "recall_at_10"),
        ("NDCG@10", "ndcg_at_10"),
        ("MRR", "mrr"),
    ]

    print(f"\nSemantic vs BM25 ({len(semantic_results)} queries)")
    print("=" * 62)
    print(f"  {'Metric':<14}{'Semantic':>12}{'BM25':>12}{'Delta':>12}{'Winner':>12}")
    for label, key in rows:
        s_val, b_val = sem[key], bm25[key]
        delta = s_val - b_val
        winner = "semantic" if s_val > b_val else ("bm25" if b_val > s_val else "tie")
        print(f"  {label:<14}{s_val:>12.4f}{b_val:>12.4f}{delta:>+12.4f}{winner:>12}")

    bm25_by_id = {r.query.id: r for r in bm25_results}
    semantic_wins = bm25_wins = ties = 0
    for r in semantic_results:
        b = bm25_by_id.get(r.query.id)
        if b is None:
            continue
        if r.rr > b.rr:
            semantic_wins += 1
        elif b.rr > r.rr:
            bm25_wins += 1
        else:
            ties += 1

    print(f"\n  Per-query MRR: semantic wins {semantic_wins}, "
          f"bm25 wins {bm25_wins}, ties {ties} (of {len(semantic_results)})")

    bm25_query_wins = [
        r for r in semantic_results
        if r.query.id in bm25_by_id and bm25_by_id[r.query.id].rr > r.rr
    ]
    if bm25_query_wins:
        print("\n  Queries where BM25 beat semantic:")
        for r in bm25_query_wins:
            b = bm25_by_id[r.query.id]
            print(f"    {r.query.id} [{r.query.type}]: \"{r.query.query}\" "
                  f"(semantic MRR={r.rr:.2f}, bm25 MRR={b.rr:.2f})")
