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


def test_validate_citations_rejects_fabricated_contradiction():
    risks = [{
        "risk": "Fabricated contradiction",
        "explanation": "The standup claims the team is on track.",
        "citations": ["standup_transcript.txt::chunk0"],
        "impact_breakdown": {"delivery_impact": "high"},
        "confidence_tag": "directional_estimate",
        "is_contradiction": True,
    }]
    evidence = [
        {
            "chunk_id": "standup_transcript.txt::chunk0",
            "text": "Still blocked. If we don't get the API credentials by Friday I don't think we make the August 14th launch date.",
        }
    ]

    validated = validate_citations(risks, evidence)
    assert validated[0]["valid"] is False
    assert validated[0]["contradiction_grounded"] is False


def test_validate_citations_rejects_single_chunk_contradiction_signal():
    risks = [{
        "risk": "Single chunk contradiction",
        "explanation": "The same chunk is claimed to show both green status and a blocker.",
        "citations": ["status_update.md::chunk0"],
        "impact_breakdown": {"delivery_impact": "high"},
        "confidence_tag": "directional_estimate",
        "is_contradiction": True,
    }]
    evidence = [
        {
            "chunk_id": "status_update.md::chunk0",
            "text": "Status: green, but we're still blocked on API credentials.",
        }
    ]

    validated = validate_citations(risks, evidence)
    assert validated[0]["valid"] is False
    assert validated[0]["contradiction_grounded"] is False


def test_validate_citations_allows_grounded_contradiction():
    risks = [{
        "risk": "Status contradiction",
        "explanation": "A green status update conflicts with the blocked launch ticket.",
        "citations": ["status_update.md::chunk0", "ticket_export.csv::ATL-142"],
        "impact_breakdown": {"delivery_impact": "high"},
        "confidence_tag": "directional_estimate",
        "is_contradiction": True,
    }]
    evidence = [
        {
            "chunk_id": "status_update.md::chunk0",
            "text": "Status: green. No blockers to flag this week.",
        },
        {
            "chunk_id": "ticket_export.csv::ATL-142",
            "text": "ticket_id: ATL-142; summary: blocked by external API credentials; status: Blocked",
        },
    ]

    validated = validate_citations(risks, evidence)
    assert validated[0]["valid"] is True
    assert validated[0]["contradiction_grounded"] is True
