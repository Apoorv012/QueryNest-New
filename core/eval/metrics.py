from __future__ import annotations

import math


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant)
    return hits / k


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    top_k = retrieved[:k]
    # `retrieved` is expected to already be deduplicated at the document
    # level (see eval/runner.py), but guard here too: without a cap, a
    # retrieved list with duplicate hits can push hits above len(relevant)
    # and recall above 1.0.
    hits = sum(1 for doc_id in top_k if doc_id in relevant)
    return min(hits / len(relevant), 1.0)


def ndcg_at_k(relevances: list[int], ideal_relevances: list[int], k: int) -> float:
    """nDCG@k, normalized against the *true* ideal ranking.

    `relevances` are the relevance scores of the retrieved results in
    retrieved order; `ideal_relevances` is the best-possible ordering
    (typically the sorted relevance scores of every known-relevant
    document from the golden set), independent of what was retrieved.
    """
    if not relevances or k <= 0:
        return 0.0

    def dcg(scores: list[int]) -> float:
        return sum(
            (2**s - 1) / math.log2(i + 2) for i, s in enumerate(scores)
        )

    actual = dcg(relevances[:k])
    ideal = dcg(sorted(ideal_relevances, reverse=True)[:k])
    if ideal == 0:
        return 0.0
    return actual / ideal


def mrr(retrieved: list[str], relevant: set[str]) -> float:
    for i, doc_id in enumerate(retrieved):
        if doc_id in relevant:
            return 1.0 / (i + 1)
    return 0.0
