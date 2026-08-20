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


def test_ndcg_at_k():
    relevances = [2, 1, 0, 0, 1]
    score = ndcg_at_k(relevances, 5)
    assert 0.0 <= score <= 1.0
    ideal = [2, 1, 1, 0, 0]
    from core.eval.metrics import ndcg_at_k as _ndcg
    ideal_score = _ndcg(ideal, 5)
    assert score <= ideal_score


def test_mrr():
    assert mrr(["b", "a", "c"], {"a"}) == 0.5
    assert mrr(["a", "b", "c"], {"a"}) == 1.0
    assert mrr(["b", "c", "d"], {"a"}) == 0.0
    assert mrr(["x", "y", "a"], {"a"}) == 1 / 3
