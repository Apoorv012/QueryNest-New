import json
from unittest.mock import Mock, patch

import pytest
import requests

from core.eval.runner import run_eval, run_search


def test_run_search_raises_on_non_2xx():
    # A stopped/misconfigured API used to be indistinguishable from a
    # retrieval failure — run_search silently returned [] instead of
    # raising (docs/plan.md 1.6).
    mock_resp = Mock()
    mock_resp.raise_for_status.side_effect = requests.HTTPError("503 Server Error")
    with patch("requests.post", return_value=mock_resp), pytest.raises(requests.HTTPError):
        run_search("test query")


def test_run_eval_dedupes_retrieved_documents_preserving_rank(tmp_path):
    golden_path = tmp_path / "golden.json"
    golden_path.write_text(
        json.dumps({
            "queries": [
                {
                    "id": "q1",
                    "query": "insurance policy",
                    "type": "semantic",
                    "expected_docs": [
                        {"document_filename": "doc_a", "relevance": 2},
                        {"document_filename": "doc_b", "relevance": 1},
                    ],
                }
            ]
        }),
        encoding="utf-8",
    )

    # 8 chunks from doc_a and 2 from doc_b, over 2 relevant docs — the kind
    # of split that used to push recall@10 above 1.0.
    raw_results = [{"document_id": "id_a"}] * 8 + [{"document_id": "id_b"}] * 2

    with patch("core.eval.runner.get_document_filename_map") as mock_map, \
         patch("core.eval.runner.run_search") as mock_search:
        mock_map.return_value = {"id_a": "doc_a", "id_b": "doc_b"}
        mock_search.return_value = (raw_results, 5.0)

        results = run_eval(golden_path, top_k=10)

    assert len(results) == 1
    pr = results[0]
    assert pr.retrieved_doc_filenames == ["doc_a", "doc_b"]
    assert len(pr.retrieved_doc_filenames) == len(set(pr.retrieved_doc_filenames))
    assert pr.recalls[10] <= 1.0
