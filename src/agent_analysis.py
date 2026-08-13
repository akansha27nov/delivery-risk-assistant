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


def analyse_risks(chunks: list[dict]) -> list[dict]:
    """
    Given reranked evidence chunks, ask the LLM to identify up to 3
    delivery risks, each grounded in at least one real chunk_id.
    """
    if not chunks:
        logger.info("No evidence chunks supplied for risk analysis.")
        return []
    evidence_text = _format_evidence(chunks)
    logger.info("Analysing %d evidence chunk(s) for delivery risks.", len(chunks))
    parsed_response = _call_llm(evidence_text)
    risks = _parse_risks_response(parsed_response)
    risks = _expand_citations_with_ticket_corroboration(risks, chunks)
    logger.info("Extracted %d risk(s) before deduplication.", len(risks))
    return _dedupe_same_ticket_risks(risks)
