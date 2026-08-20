from core.eval.metrics import mrr, ndcg_at_k, precision_at_k, recall_at_k


def test_precision_at_k():
    retrieved = ["a", "b", "c", "d", "e"]
    relevant = {"a", "c", "e"}
    assert precision_at_k(retrieved, relevant, 5) == 3 / 5
    assert precision_at_k(retrieved, relevant, 3) == 2 / 3
    assert precision_at_k(retrieved, relevant, 0) == 0.0


def test_recall_at_k():
    retrieved = ["a", "b", "c"]
    relevant = {"a", "c", "e", "f"}
    assert recall_at_k(retrieved, relevant, 3) == 2 / 4
    assert recall_at_k(retrieved, relevant, 5) == 2 / 4
    assert recall_at_k(retrieved, set(), 3) == 0.0


def test_recall_at_k_never_exceeds_one_with_duplicates():
    # An 8+2 chunk split over 2 relevant docs, passed in without dedup,
    # used to yield recall@10 == 5.0 (docs/plan.md 1.1).
    retrieved = ["a"] * 8 + ["b"] * 2
    relevant = {"a", "b"}
    score = recall_at_k(retrieved, relevant, 10)
    assert 0.0 <= score <= 1.0
    assert score == 1.0


def test_ndcg_at_k():
    relevances = [2, 1, 0, 0, 1]
    ideal = [2, 1, 1, 0, 0]
    score = ndcg_at_k(relevances, ideal, 5)
    assert 0.0 <= score <= 1.0
    ideal_score = ndcg_at_k(ideal, ideal, 5)
    assert score <= ideal_score
    assert ideal_score == 1.0


def test_ndcg_at_k_penalizes_mediocre_results_against_true_ideal():
    # All-1s retrieved in perfect (descending) order used to score a false
    # 1.0 because IDCG was computed from the retrieved list itself, instead
    # of from the golden set's true ideal ranking (docs/plan.md 1.2).
    relevances = [1] * 10
    ideal_relevances = [2, 2, 1, 1, 1, 1, 1, 1, 1, 1]
    score = ndcg_at_k(relevances, ideal_relevances, 10)
    assert score < 1.0


def test_mrr():
    assert mrr(["b", "a", "c"], {"a"}) == 0.5
    assert mrr(["a", "b", "c"], {"a"}) == 1.0
    assert mrr(["b", "c", "d"], {"a"}) == 0.0
    assert mrr(["x", "y", "a"], {"a"}) == 1 / 3
