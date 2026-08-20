from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .runner import QueryResult, get_git_commit


def generate_report(
    results: list[QueryResult],
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    commit = get_git_commit()
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")

    all_precisions = {5: [], 10: []}
    all_recalls = {5: [], 10: []}
    all_ndcg = {10: []}
    all_rr = []
    all_latencies = []

    by_type: dict[str, list[QueryResult]] = {}
    for r in results:
        by_type.setdefault(r.query.type, []).append(r)

    for r in results:
        for k in [5, 10]:
            all_precisions[k].append(r.precisions.get(k, 0))
            all_recalls[k].append(r.recalls.get(k, 0))
        all_ndcg[10].append(r.ndcg.get(10, 0))
        all_rr.append(r.rr)
        all_latencies.append(r.latency_ms)

    def avg(vals: list[float]) -> float:
        return sum(vals) / len(vals) if vals else 0.0

    report = {
        "timestamp": timestamp,
        "git_commit": commit,
        "total_queries": len(results),
        "metrics": {
            "precision_at_5": round(avg(all_precisions[5]), 4),
            "precision_at_10": round(avg(all_precisions[10]), 4),
            "recall_at_5": round(avg(all_recalls[5]), 4),
            "recall_at_10": round(avg(all_recalls[10]), 4),
            "ndcg_at_10": round(avg(all_ndcg[10]), 4),
            "mrr": round(avg(all_rr), 4),
        },
        "latency_ms_avg": round(avg(all_latencies), 1),
        "by_type": {},
        "worst_queries": [],
        "query_results": [],
    }

    for qtype, type_results in sorted(by_type.items()):
        report["by_type"][qtype] = {
            "count": len(type_results),
            "precision_at_5": round(avg([r.precisions.get(5, 0) for r in type_results]), 4),
            "recall_at_10": round(avg([r.recalls.get(10, 0) for r in type_results]), 4),
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

    filename = f"report_{timestamp}_{commit}.json"
    output_path = output_dir / filename
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return output_path


def print_report(results: list[QueryResult]) -> None:
    all_precisions = {5: [], 10: []}
    all_recalls = {5: [], 10: []}
    all_ndcg = {10: []}
    all_rr = []

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
