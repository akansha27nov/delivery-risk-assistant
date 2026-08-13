"""
Citation, context, and contradiction validation helpers.
"""

import re

from logger import get_logger

logger = get_logger(__name__)

_ENTITY_ID_PATTERN = re.compile(r"\b([A-Z]{2,8})-\d+\b")
_STATUS_CLAIM_PHRASES = ("on track", "green", "no blockers", "all good", "no issues to flag")
_CONTRADICTION_SIGNAL_PHRASES = (
    "blocked",
    "blocking",
    "delay",
    "delayed",
    "late",
    "at risk",
    "missed",
    "won't make",
    "wont make",
    "not make",
    "can't make",
    "cannot make",
    "slip",
    "slipping",
    "unassigned",
    "sev-1",
)


def _extract_entity_prefixes(text: str) -> set:
    """Pull ticket-style identifier prefixes out of a chunk's text."""
    return {m.upper() for m in _ENTITY_ID_PATTERN.findall(text or "")}


def _chunk_text_has_any(text: str, phrases: tuple[str, ...]) -> bool:
    lowered = (text or "").lower()
    return any(phrase in lowered for phrase in phrases)


def _has_grounded_status_claim(citations: list[str], evidence_map: dict) -> bool:
    for cid in citations:
        text = evidence_map.get(cid, {}).get("text") or ""
        if _chunk_text_has_any(text, _STATUS_CLAIM_PHRASES):
            return True
    return False


def _has_grounded_contradiction(citations: list[str], evidence_map: dict) -> bool:
    status_citations = [
        cid for cid in citations
        if _chunk_text_has_any(evidence_map.get(cid, {}).get("text") or "", _STATUS_CLAIM_PHRASES)
    ]
    problem_citations = [
        cid for cid in citations
        if _chunk_text_has_any(evidence_map.get(cid, {}).get("text") or "", _CONTRADICTION_SIGNAL_PHRASES)
    ]

    # A contradiction must be supported by two distinct pieces of evidence:
    # one chunk that actually makes a positive status claim and another chunk
    # that actually describes the blocking/problem condition.
    return bool(status_citations and problem_citations and set(status_citations) != set(problem_citations))


def _check_context_consistency(valid_cites: list, evidence_map: dict):
    """
    Check whether cited chunks describe the same project context.
    """
    prefix_groups = {}
    for cid in valid_cites:
        prefixes = _extract_entity_prefixes(evidence_map.get(cid, {}).get("text", ""))
        if prefixes:
            prefix_groups[cid] = prefixes

    if len(prefix_groups) < 2:
        return True, ""

    common = set.intersection(*prefix_groups.values())
    if common:
        return True, ""

    conflict_desc = "; ".join(f"{cid} mentions {sorted(p)}" for cid, p in prefix_groups.items())
    return False, f"Citations reference unrelated entity groups with no overlap -- {conflict_desc}"


def validate_citations(risks: list[dict], evidence) -> list[dict]:
    """
    Validates citations, impact breakdown, and computes transparent Evidence Confidence.
    """
    evidence_map = {}
    all_scores = []
    if evidence and isinstance(next(iter(evidence), None), dict):
        evidence_map = {c.get("chunk_id"): c for c in evidence}
        known_ids = set(evidence_map.keys())
        all_scores = [c.get("rerank_score", c.get("score", 0.0)) for c in evidence]
    else:
        known_ids = set(evidence) if evidence else set()

    validated = []
    for r in risks:
        valid_cites = [c for c in r.get("citations", []) if c in known_ids]
        has_valid_citation = len(valid_cites) > 0

        has_impact = r.get("impact_breakdown") is not None
        has_confidence_tag = r.get("confidence_tag") is not None

        context_consistent, context_mismatch_detail = True, ""
        if evidence_map and has_valid_citation:
            context_consistent, context_mismatch_detail = _check_context_consistency(
                valid_cites, evidence_map
            )

        contradiction_grounded = True
        if r.get("is_contradiction"):
            contradiction_grounded = False
            if evidence_map and has_valid_citation:
                contradiction_grounded = _has_grounded_contradiction(valid_cites, evidence_map)

        is_valid = (
            has_valid_citation and has_impact and has_confidence_tag
            and context_consistent and contradiction_grounded
        )

        base_score = 20.0
        citation_score = 30.0 if has_valid_citation else 0.0
        num_citations = len(valid_cites)
        unique_docs = len({c.split("::")[0] for c in valid_cites})
        supporting_docs_score = min(unique_docs * 8.33, 25.0)

        percentile = 0.5
        if evidence_map and num_citations > 0 and all_scores:
            cited_scores = [
                evidence_map.get(c, {}).get("rerank_score", evidence_map.get(c, {}).get("score", 0.0))
                for c in valid_cites
            ]
            avg_cited_score = sum(cited_scores) / len(cited_scores)
            percentile = sum(1 for s in all_scores if avg_cited_score >= s) / len(all_scores)
        rerank_score_component = percentile * 25.0

        total_score = base_score + citation_score + supporting_docs_score + rerank_score_component
        evidence_confidence = int(min(max(total_score, 10), 99))

        if not context_consistent:
            evidence_confidence = min(evidence_confidence, 20)

        if percentile >= 0.66:
            retrieval_quality = "High"
        elif percentile >= 0.33:
            retrieval_quality = "Medium"
        else:
            retrieval_quality = "Low"

        r["valid"] = is_valid
        r["citations"] = valid_cites
        r["evidence_confidence"] = evidence_confidence
        r["context_consistent"] = context_consistent
        r["contradiction_grounded"] = contradiction_grounded
        r["context_mismatch_detail"] = context_mismatch_detail
        r["confidence_breakdown"] = {
            "citation_valid": has_valid_citation,
            "num_docs": unique_docs,
            "retrieval_quality": retrieval_quality,
            "context_consistent": context_consistent,
        }
        validated.append(r)

    return validated
