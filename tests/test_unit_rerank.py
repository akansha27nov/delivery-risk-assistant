# tests/test_unit_rerank.py
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import rerank

def test_rerank_empty_chunks():
    """Verify rerank returns an empty list immediately when given no chunks."""
    result = rerank.rerank("What is the launch status?", [])
    assert result == []


@patch("rerank.cohere.Client")
def test_rerank_success(mock_cohere_client):
    """Verify rerank correctly invokes Cohere API and maps relevance scores."""
    mock_client_inst = MagicMock()
    mock_cohere_client.return_value = mock_client_inst

    mock_res_item = MagicMock()
    mock_res_item.index = 0
    mock_res_item.relevance_score = 0.95

    mock_response = MagicMock()
    mock_response.results = [mock_res_item]
    mock_client_inst.rerank.return_value = mock_response

    with patch.object(rerank, "co", mock_client_inst):
        chunks = [{
            "chunk_id": "c1",
            "source": "charter.md",
            "location": "charter.md — Sec 1",
            "text": "Launch date is on track.",
            "project": "atlas"
        }]

        output = rerank.rerank("Is launch on track?", chunks, top_n=5)
        
        assert len(output) == 1
        assert output[0]["rerank_score"] == 0.95
        assert output[0]["chunk_id"] == "c1"