# src/test_agent.py
from agent import validate_citations, _parse_risks_response

mock_raw_response = '{"risks": [{"risk": "Test Risk", "citations": ["chunk_1"], "confidence_tag": "invalid_tag", "cost_estimate": ""}]}'
parsed = _parse_risks_response(mock_raw_response)

print("Parsed Risk:", parsed[0])
assert parsed[0]["confidence_tag"] is None, "Failed: Invalid confidence tag was not set to None"
assert parsed[0]["cost_estimate"] is None, "Failed: Empty cost estimate was not set to None"

# Pass evidence chunks or a list of known IDs positionally
validated = validate_citations(parsed, [{"chunk_id": "chunk_1"}])
print("Validation Result:", validated[0]["valid"])
assert validated[0]["valid"] is False, "Failed: Risk with missing cost/tag passed validation!"

print("✅ Agent validation checks passed!")