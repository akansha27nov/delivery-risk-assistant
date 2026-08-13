"""
LLM-backed risk extraction helpers.
"""

import re
from typing import Optional
from openai import OpenAI
from config import OPENAI_API_KEY, LLM_MODEL
from logger import get_logger
from prompts import SYSTEM_PROMPT
from agent_models import RiskExtractionResponse
from agent_validation import _chunk_text_has_any, _STATUS_CLAIM_PHRASES, _CONTRADICTION_SIGNAL_PHRASES

logger = get_logger(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

_TICKET_ID_PATTERN = re.compile(r"\b[A-Z]{2,8}-\d+\b")


def _format_evidence(chunks: list[dict]) -> str:
    """Pure formatting, no LLM call -- testable on its own."""
    blocks = []
    for c in chunks:
        blocks.append(f"chunk_id: {c['chunk_id']}\nsource: {c['location']}\ntext: {c['text']}")
    return "\n---\n".join(blocks)


def _call_llm(evidence_text: str) -> Optional[RiskExtractionResponse]:
    """Calls OpenAI using structured outputs with Pydantic schema enforcement."""
    try:
        logger.debug("Calling OpenAI structured extraction with %d characters of evidence.", len(evidence_text))
        completion = client.beta.chat.completions.parse(
            model=LLM_MODEL,
            temperature=0,
            seed=42,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Evidence:\n\n{evidence_text}"},
            ],
            response_format=RiskExtractionResponse,
        )
        return completion.choices[0].message.parsed
    except Exception as e:
        logger.exception("OpenAI structured parsing error: %s", e)
        return None


def _parse_risks_response(parsed_response: Optional[RiskExtractionResponse]) -> list[dict]:
    """Convert parsed Pydantic response object to list of dicts for LangGraph state compatibility."""
    if not parsed_response or not parsed_response.risks:
        return []

    parsed_risks = []
    for risk in parsed_response.risks:
        parsed_risks.append({
            "risk": risk.risk,
            "explanation": risk.explanation,
            "citations": risk.citations,
            "impact_breakdown": risk.impact_breakdown.model_dump(),
            "confidence_tag": risk.confidence_tag,
            "is_sev1": risk.is_sev1,
            "is_contradiction": risk.is_contradiction,
            "recommendations": risk.recommendations
        })
    return parsed_risks


def _find_duplicate_risk_indices(risks: list[dict]) -> set:
    """
    Deterministic backstop for the specific pattern Rule 9 targets.
    """
    to_drop = set()
    for i in range(len(risks)):
        if i in to_drop:
            continue
        ids_i = set(_TICKET_ID_PATTERN.findall(risks[i].get("explanation", "") + " " + risks[i].get("risk", "")))
        cites_i = set(risks[i].get("citations", []))
        for j in range(i + 1, len(risks)):
            if j in to_drop:
                continue
            ids_j = set(_TICKET_ID_PATTERN.findall(risks[j].get("explanation", "") + " " + risks[j].get("risk", "")))
            cites_j = set(risks[j].get("citations", []))
            if ids_i and ids_j and (ids_i & ids_j) and (cites_i & cites_j):
                to_drop.add(j if len(cites_i) >= len(cites_j) else i)
    return to_drop


def _expand_citations_with_ticket_corroboration(risks: list[dict], chunks: list[dict]) -> list[dict]:
    """
    Guarantees the citation list includes every chunk that references the same specific
    ticket ID the risk's own text already names.
    """
    for r in risks:
        ids_in_risk = set(_TICKET_ID_PATTERN.findall(r.get("explanation", "") + " " + r.get("risk", "")))
        if not ids_in_risk:
            continue
        existing = set(r.get("citations", []))
        for c in chunks:
            cid = c.get("chunk_id")
            if cid in existing:
                continue
            chunk_ids = set(_TICKET_ID_PATTERN.findall(c.get("text", "") or ""))
            if chunk_ids & ids_in_risk:
                existing.add(cid)
        r["citations"] = sorted(existing)
    return risks


def _dedupe_same_ticket_risks(risks: list[dict]) -> list[dict]:
    drop = _find_duplicate_risk_indices(risks)
    return [r for i, r in enumerate(risks) if i not in drop]

def _find_missed_contradiction_candidates(chunks: list[dict], risks: list[dict]) -> list[tuple[dict, dict]]:
    """
    Deterministic pre-check over the FULL evidence pool, independent of what
    the first extraction pass found. A single large-context pass can miss a
    real status-vs-problem pair even when the model would judge it correctly
    if shown just those two chunks in isolation -- this finds every pair the
    phrase lists flag as a candidate, so nothing depends on the model
    noticing it unprompted.
    """
    status_chunks = [c for c in chunks if _chunk_text_has_any(c.get("text", ""), _STATUS_CLAIM_PHRASES)]
    problem_chunks = [c for c in chunks if _chunk_text_has_any(c.get("text", ""), _CONTRADICTION_SIGNAL_PHRASES)]

    already_covered = set()
    for r in risks:
        if r.get("is_contradiction"):
            already_covered.update(r.get("citations", []))

    candidates = []
    for sc in status_chunks:
        for pc in problem_chunks:
            if sc["chunk_id"] == pc["chunk_id"]:
                continue
            if sc["chunk_id"] in already_covered and pc["chunk_id"] in already_covered:
                continue  # first pass already produced a contradiction risk covering this pair
            candidates.append((sc, pc))
    return candidates

def _find_missed_contradiction_candidate_groups(chunks: list[dict], risks: list[dict]):
    """
    Groups problem chunks by ticket ID (same pattern _expand_citations_with_ticket_corroboration
    already uses) before checking for a missed contradiction. A raw pairwise cross product
    produced multiple near-duplicate risks about the same ticket -- grouping collapses those
    into one targeted check per real underlying issue, while still guaranteeing every candidate
    gets an explicit, isolated judgment instead of depending on the model to notice it in a
    large context.
    """
    status_chunks = [c for c in chunks if _chunk_text_has_any(c.get("text", ""), _STATUS_CLAIM_PHRASES)]
    problem_chunks = [c for c in chunks if _chunk_text_has_any(c.get("text", ""), _CONTRADICTION_SIGNAL_PHRASES)]
    if not status_chunks or not problem_chunks:
        return []

    already_covered = set()
    for r in risks:
        if r.get("is_contradiction"):
            already_covered.update(r.get("citations", []))

    groups: dict[str, list[dict]] = {}
    for pc in problem_chunks:
        if pc["chunk_id"] in already_covered:
            continue
        ids = _TICKET_ID_PATTERN.findall(pc.get("text", "") or "")
        key = ids[0] if ids else f"__chunk__{pc['chunk_id']}"
        groups.setdefault(key, []).append(pc)

    return [(status_chunks, group) for group in groups.values()]


def _call_llm_targeted_contradiction_check(status_chunks: list[dict], problem_chunks: list[dict]):
    """Forces one explicit judgment per real underlying issue, not per raw chunk pair."""
    evidence_text = _format_evidence(status_chunks + problem_chunks)
    try:
        completion = client.beta.chat.completions.parse(
            model=LLM_MODEL, temperature=0, seed=42,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": (
                    "Evidence -- determine ONLY whether any status-claim chunk here "
                    f"contradicts the problem chunk(s) below, per Rule 4:\n\n{evidence_text}"
                )},
            ],
            response_format=RiskExtractionResponse,
        )
        parsed = completion.choices[0].message.parsed
        if parsed and parsed.risks:
            for r in parsed.risks:
                if r.is_contradiction:
                    return r
        return None
    except Exception as e:
        logger.exception("Targeted contradiction check failed: %s", e)
        return None
    
def analyse_risks(chunks: list[dict]) -> list[dict]:
    if not chunks:
        logger.info("No evidence chunks supplied for risk analysis.")
        return []

    evidence_text = _format_evidence(chunks)
    logger.info(
        "Analysing %d evidence chunk(s) for delivery risks.",
        len(chunks),
    )

    # ---------------------------------------------------------
    # Pass 1: normal extraction
    # ---------------------------------------------------------
    parsed_response = _call_llm(evidence_text)
    risks = _parse_risks_response(parsed_response)

    risks = _expand_citations_with_ticket_corroboration(
        risks,
        chunks,
    )

    # ---------------------------------------------------------
    # Pass 2: targeted contradiction detection
    # ---------------------------------------------------------
    candidate_groups = _find_missed_contradiction_candidate_groups(
        chunks,
        risks,
    )

    for status_chunks, problem_chunks in candidate_groups:
        forced = _call_llm_targeted_contradiction_check(
            status_chunks,
            problem_chunks,
        )

        if not forced:
            continue

        status_ids = {c["chunk_id"] for c in status_chunks}
        problem_ids = {c["chunk_id"] for c in problem_chunks}

        # If the first pass already found a contradiction involving
        # the same status evidence, keep the first-pass risk.
        # This prevents two descriptions of the same underlying
        # contradiction from becoming two separate risks.
        already_has_same_contradiction = False

        for existing in risks:
            if not existing.get("is_contradiction"):
                continue

            existing_citations = set(
                existing.get("citations", [])
            )

            if existing_citations & status_ids:
                already_has_same_contradiction = True
                break

        if already_has_same_contradiction:
            logger.info(
                "Skipping targeted contradiction because an existing "
                "contradiction already covers the same status evidence "
                "(status chunks: %s).",
                ", ".join(sorted(status_ids)),
            )
            continue

        logger.warning(
            "First-pass extraction missed a contradiction "
            "(problem chunk(s): %s)",
            ", ".join(sorted(problem_ids)),
        )

        # IMPORTANT:
        # Use ONLY the citations returned by the targeted LLM.
        # Do NOT union every problem/status chunk here.
        forced_citations = set(forced.citations)

        # Make sure the targeted risk is grounded in the actual
        # candidate evidence, but don't add unrelated chunks.
        valid_chunk_ids = {
            c["chunk_id"] for c in chunks
        }

        forced_citations &= valid_chunk_ids

        risks.append({
            "risk": forced.risk,
            "explanation": forced.explanation,
            "citations": sorted(forced_citations),
            "impact_breakdown": (
                forced.impact_breakdown.model_dump()
            ),
            "confidence_tag": forced.confidence_tag,
            "is_sev1": forced.is_sev1,
            "is_contradiction": True,
            "recommendations": forced.recommendations,
        })

    risks = _expand_citations_with_ticket_corroboration(
        risks,
        chunks,
    )

    logger.info(
        "Extracted %d risk(s) before deduplication.",
        len(risks),
    )

    return _dedupe_same_ticket_risks(risks)