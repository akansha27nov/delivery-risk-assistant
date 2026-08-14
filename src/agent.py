"""
Compatibility facade for the reasoning and trust layer.

The implementation lives in smaller modules:
- agent_models.py
- agent_analysis.py
- agent_validation.py
"""

from agent_models import ImpactBreakdown, RiskExtractionResponse, RiskItem
from agent_analysis import (
    _call_llm,
    _call_llm_targeted_contradiction_check,
    _dedupe_same_ticket_risks,
    _expand_citations_with_ticket_corroboration,
    _find_duplicate_risk_indices,
    _format_evidence,
    _parse_risks_response,
    analyse_risks,
)
from agent_validation import (
    _check_context_consistency,
    _chunk_text_has_any,
    _extract_entity_prefixes,
    _has_grounded_contradiction,
    _has_grounded_status_claim,
    validate_citations,
)

__all__ = [
    "ImpactBreakdown",
    "RiskExtractionResponse",
    "RiskItem",
    "_call_llm",
    "_check_context_consistency",
    "_chunk_text_has_any",
    "_dedupe_same_ticket_risks",
    "_expand_citations_with_ticket_corroboration",
    "_extract_entity_prefixes",
    "_find_duplicate_risk_indices",
    "_format_evidence",
    "_has_grounded_contradiction",
    "_has_grounded_status_claim",
    "_parse_risks_response",
    "_call_llm_targeted_contradiction_check",
    "analyse_risks",
    "validate_citations",
]