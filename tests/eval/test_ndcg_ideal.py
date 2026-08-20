"""Regression: nDCG must reach 1.0 for perfect retrieval even when the golden
set lists the same document more than once (two passages, one document)."""
from core.eval.metrics import ndcg_at_k


def _ideal_from(expected: list[tuple[str, int]]) -> list[int]:
    best: dict[str, int] = {}
    for name, rel in expected:
        best[name] = max(best.get(name, 0), rel)
    return list(best.values())


def test_perfect_retrieval_scores_one_despite_duplicate_expected_docs():
    # Golden set names bert_2018 twice (two passages) but it is one document.
    expected = [("bert_2018", 2), ("bert_2018", 2)]
    ideal = _ideal_from(expected)
    # Deduped retrieval can only ever return the document once.
    assert ndcg_at_k([2], ideal, 10) == 1.0


def test_missing_a_relevant_document_still_penalized():
    expected = [("a", 2), ("a", 1), ("b", 2)]
    ideal = _ideal_from(expected)
    assert ndcg_at_k([2], ideal, 10) < 1.0
