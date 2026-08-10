import pytest
from agent import _check_context_consistency, _format_evidence, validate_citations

def test_format_evidence():
    chunks = [
        {"chunk_id": "c1", "location": "loc1", "text": "Sample text 1"},
        {"chunk_id": "c2", "location": "loc2", "text": "Sample text 2"}
    ]
    formatted = _format_evidence(chunks)
    assert "chunk_id: c1" in formatted
    assert "chunk_id: c2" in formatted

def test_check_context_consistency_mismatch():
    evidence_map = {
        "c1": {"text": "Ticket ATL-101 blocked"},
        "c2": {"text": "Ticket ORION-202 delayed"}
    }
    # Citations from non-overlapping entity groups should report mismatch
    consistent, detail = _check_context_consistency(["c1", "c2"], evidence_map)
    assert consistent is False
    assert "unrelated entity groups" in detail

def test_validate_citations_context_mismatch_caps_confidence():
    risks = [{
        "risk": "Conflicting Risk",
        "citations": ["c1", "c2"],
        "impact_breakdown": {"delivery_impact": "high"},
        "confidence_tag": "directional_estimate"
    }]
    evidence = [
        {"chunk_id": "c1", "text": "Issue in ATL-100"},
        {"chunk_id": "c2", "text": "Issue in ORION-500"}
    ]
    
    validated = validate_citations(risks, evidence)
    assert validated[0]["valid"] is False
    assert validated[0]["evidence_confidence"] <= 20