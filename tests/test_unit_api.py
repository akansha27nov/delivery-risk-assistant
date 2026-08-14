# tests/test_unit_api.py
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import api

client = TestClient(api.app)


@patch("api.run_pipeline")
def test_trigger_audit_success(mock_run_pipeline):
    """Verify successful audit trigger returns pipeline results."""
    mock_run_pipeline.return_value = {"status": "success", "summary": "All clear"}
    response = client.post(
        "/run-audit", json={"project": "atlas", "question": "Are there blockers?"}
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success", "summary": "All clear"}
    mock_run_pipeline.assert_called_once_with(
        project="atlas", question="Are there blockers?"
    )


@patch("api.run_pipeline")
def test_trigger_audit_exception(mock_run_pipeline):
    """Verify that exceptions in the pipeline are caught and returned as HTTP 500 errors."""
    mock_run_pipeline.side_effect = Exception("Pipeline execution failed")
    response = client.post("/run-audit", json={"project": "atlas"})

    assert response.status_code == 500
    assert "Pipeline execution failed" in response.json()["detail"]
