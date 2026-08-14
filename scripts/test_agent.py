# src/test_agent.py
from agent import (
    ImpactBreakdown,
    RiskExtractionResponse,
    RiskItem,
    _parse_risks_response,
    validate_citations,
)

# 1. Test Pydantic model parsing and conversion
mock_item = RiskItem(
    risk="Test Risk",
    explanation="Test explanation",
    citations=["chunk_1"],
    impact_breakdown=ImpactBreakdown(
        delivery_impact="Delay",
        customer_impact="None",
        business_impact="None",
        team_impact="High",
    ),
    confidence_tag="directional_estimate",  # <-- FIX: Use a valid tag
    is_sev1=False,
    is_contradiction=False,
    recommendations=["Rec 1", "Rec 2"],
)

mock_response = RiskExtractionResponse(risks=[mock_item])
parsed = _parse_risks_response(mock_response)

print("Parsed Risk:", parsed[0])

# 2. Test Citation Validation
# We must include a dummy 'rerank_score' if your validator expects it,
# but simply matching the chunk_id is usually enough for the valid test.
validated = validate_citations(parsed, [{"chunk_id": "chunk_1", "rerank_score": 0.9}])
print("Validation Result (Valid Chunk):", validated[0]["valid"])
assert validated[0]["valid"] is True, "Failed: Valid citation failed validation!"

# Test invalid citation ID
unvalidated = validate_citations(parsed, [{"chunk_id": "different_chunk"}])
print("Validation Result (Missing Chunk):", unvalidated[0]["valid"])
assert unvalidated[0]["valid"] is False, "Failed: Invalid citation passed validation!"

print("✅ Agent validation checks passed!")
