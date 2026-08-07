import os
import sys
import pytest
from unittest.mock import patch
# Ensure the src directory is in the Python path so 'agent' can be found
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from agent import (
    _format_evidence,
    _parse_risks_response,
    validate_citations,
    analyse_risks,
    RiskExtractionResponse,
    RiskItem
)

def test_format_evidence():
    """Test pure formatting of evidence chunks."""
    chunks = [
        {"chunk_id": "sprint_report.md::chunk1", "location": "sprint_report.md", "text": "Velocity is down."}
    ]
    result = _format_evidence(chunks)
    assert "chunk_id: sprint_report.md::chunk1" in result
    assert "source: sprint_report.md" in result
    assert "text: Velocity is down." in result


def test_validate_citations_valid():
    """Test citation validation filters out hallucinated chunk IDs and checks required fields."""
    risks = [
        {
            "risk": "Declining velocity",
            "explanation": "Velocity dropped in sprint 14.",
            "citations": ["sprint_report.md::chunk1", "hallucinated::chunk99"],
            "cost_estimate": "Project delay risk",
            "confidence_tag": "directional_estimate",
            "is_sev1": False,
            "is_contradiction": False
        }
    ]
    evidence = [{"chunk_id": "sprint_report.md::chunk1"}]
    validated = validate_citations(risks, evidence)
    
    assert validated[0]["valid"] is True
    assert validated[0]["citations"] == ["sprint_report.md::chunk1"]


def test_validate_citations_missing_required_fields():
    """Test that a risk fails validation if cost_estimate or confidence_tag is missing."""
    risks = [
        {
            "risk": "Incomplete Risk",
            "explanation": "Missing mandatory metadata.",
            "citations": ["sprint_report.md::chunk1"],
            "cost_estimate": None,
            "confidence_tag": None,
            "is_sev1": False,
            "is_contradiction": False
        }
    ]
    evidence = [{"chunk_id": "sprint_report.md::chunk1"}]
    validated = validate_citations(risks, evidence)
    
    assert validated[0]["valid"] is False


@patch("agent.client.beta.chat.completions.parse")
def test_analyse_risks_mocked(mock_parse):
    """Test `analyse_risks` with a mocked OpenAI structured output response."""
    mock_response = RiskExtractionResponse(
        risks=[
            RiskItem(
                risk="Status contradiction detected",
                explanation="Status report says green while ticket is blocked.",
                citations=["sprint_report.md::chunk2"],
                cost_estimate="Delayed partner launch",
                confidence_tag="directional_estimate",
                is_sev1=False,
                is_contradiction=True
            )
        ]
    )
    mock_parse.return_value.choices[0].message.parsed = mock_response

    chunks = [{"chunk_id": "sprint_report.md::chunk2", "location": "sprint_report.md", "text": "Blocked."}]
    result = analyse_risks(chunks)

    assert len(result) == 1
    assert result[0]["risk"] == "Status contradiction detected"
    assert result[0]["is_contradiction"] is True
    assert result[0]["citations"] == ["sprint_report.md::chunk2"]