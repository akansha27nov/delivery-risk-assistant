"""
LLM-backed risk extraction helpers.

  - Grounding pre-check: a contradiction is only accepted if its citations contain
    BOTH a real status claim AND a real problem signal. This stops fabricated
    contradictions from entering the pipeline and rejecting the whole report, while preserving
    genuine contradictions.
  - Removed the over-aggressive fallback that treated every non-problem chunk as a
    status claim.
  - Pair-based skip logic (keeps the SEV-1 contradiction when a status chunk is
    shared across two problem chunks).
  - Stable chunk ordering + semantic contradiction dedup.
"""

import re

from openai import OpenAI

from agent_models import RiskExtractionResponse
from agent_validation import (
    _CONTRADICTION_SIGNAL_PHRASES,
    _STATUS_CLAIM_PHRASES,
    _chunk_text_has_any,
)
from config import LLM_MODEL, OPENAI_API_KEY
from logger import get_logger
from prompts import SYSTEM_PROMPT

logger = get_logger(__name__)
client = OpenAI(api_key=OPENAI_API_KEY)

_TICKET_ID_PATTERN = re.compile(r"\b[A-Z]{2,8}-\d+\b")


def _format_evidence(chunks: list[dict]) -> str:
    """Pure formatting, no LLM call -- testable on its own."""
    blocks = []
    for c in chunks:
        blocks.append(
            f"chunk_id: {c['chunk_id']}\nsource: {c['location']}\ntext: {c['text']}"
        )
    return "\n---\n".join(blocks)


def _call_llm(evidence_text: str) -> RiskExtractionResponse | None:
    """Calls OpenAI using structured outputs with Pydantic schema enforcement."""
    try:
        logger.debug(
            "Calling OpenAI structured extraction with %d characters of evidence.",
            len(evidence_text),
        )
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


def _parse_risks_response(parsed_response: RiskExtractionResponse | None) -> list[dict]:
    """Convert parsed Pydantic response object to list of dicts for LangGraph state compatibility."""
    if not parsed_response or not parsed_response.risks:
        return []

    parsed_risks = []
    for risk in parsed_response.risks:
        parsed_risks.append(
            {
                "risk": risk.risk,
                "explanation": risk.explanation,
                "citations": risk.citations,
                "impact_breakdown": risk.impact_breakdown.model_dump(),
                "confidence_tag": risk.confidence_tag,
                "is_sev1": risk.is_sev1,
                "is_contradiction": risk.is_contradiction,
                "recommendations": risk.recommendations,
            }
        )
    return parsed_risks


def _is_grounded_contradiction(risk: dict, chunks: list[dict]) -> bool:
    """
    A contradiction is only grounded if its citations include at least one chunk
    that makes a positive status claim AND at least one chunk that carries a
    problem/blocking signal. This is the same rule the validator uses, applied
    EARLY so fabricated contradictions never enter the pipeline.
    """
    chunk_map = {c.get("chunk_id"): c for c in chunks}
    cites = set(risk.get("citations", []))
    has_status = any(
        _chunk_text_has_any(chunk_map.get(c, {}).get("text", ""), _STATUS_CLAIM_PHRASES)
        for c in cites
    )
    has_problem = any(
        _chunk_text_has_any(
            chunk_map.get(c, {}).get("text", ""), _CONTRADICTION_SIGNAL_PHRASES
        )
        for c in cites
    )
    return has_status and has_problem


def _find_duplicate_risk_indices(risks: list[dict]) -> set:
    """
    Deterministic backstop for the specific pattern Rule 9 targets.
    Enhanced to catch exact title/citation duplicates when ticket IDs are missing.
    """
    to_drop = set()
    for i in range(len(risks)):
        if i in to_drop:
            continue

        r_i = risks[i]
        ids_i = set(
            _TICKET_ID_PATTERN.findall(
                r_i.get("explanation", "") + " " + r_i.get("risk", "")
            )
        )
        cites_i = set(r_i.get("citations", []))
        title_i = r_i.get("risk", "").strip().lower()

        for j in range(i + 1, len(risks)):
            if j in to_drop:
                continue

            r_j = risks[j]
            ids_j = set(
                _TICKET_ID_PATTERN.findall(
                    r_j.get("explanation", "") + " " + r_j.get("risk", "")
                )
            )
            cites_j = set(r_j.get("citations", []))
            title_j = r_j.get("risk", "").strip().lower()

            # Rule 1: Shared ticket IDs and overlapping citations (Your original rule)
            if (
                ids_i
                and ids_j
                and (ids_i & ids_j)
                and (cites_i & cites_j)
                or title_i
                and title_i == title_j
                or not ids_i
                and not ids_j
                and cites_i
                and cites_i == cites_j
            ):
                to_drop.add(j if len(cites_i) >= len(cites_j) else i)

    return to_drop


def _expand_citations_with_ticket_corroboration(
    risks: list[dict], chunks: list[dict]
) -> list[dict]:
    """Guarantees the citation list includes every chunk referencing the same ticket ID."""
    for r in risks:
        ids_in_risk = set(
            _TICKET_ID_PATTERN.findall(
                r.get("explanation", "") + " " + r.get("risk", "")
            )
        )
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


def _dedupe_contradiction_risks(risks: list[dict], chunks: list[dict]) -> list[dict]:
    """Merges near-duplicate contradictions that share a status chunk + overlapping problem chunks."""
    chunk_map = {c.get("chunk_id"): c for c in chunks}

    def classify(r: dict) -> tuple[set, set]:
        cites = set(r.get("citations", []))
        status = {
            c
            for c in cites
            if _chunk_text_has_any(
                chunk_map.get(c, {}).get("text", ""), _STATUS_CLAIM_PHRASES
            )
        }
        problem = {
            c
            for c in cites
            if _chunk_text_has_any(
                chunk_map.get(c, {}).get("text", ""), _CONTRADICTION_SIGNAL_PHRASES
            )
        }
        return status, problem

    contradictions = [r for r in risks if r.get("is_contradiction")]
    others = [r for r in risks if not r.get("is_contradiction")]

    keep: list[dict] = []
    for r in contradictions:
        r_status, r_problem = classify(r)
        if not r_status or not r_problem:
            keep.append(r)
            continue
        duplicate = False
        for k in keep:
            k_status, k_problem = classify(k)
            if (r_status & k_status) and (r_problem & k_problem):
                if len(r.get("citations", [])) <= len(k.get("citations", [])):
                    duplicate = True
                    break
        if not duplicate:
            keep.append(r)

    return others + keep


def _find_missed_contradiction_candidate_groups(chunks: list[dict], risks: list[dict]):
    """
    Groups problem chunks by ticket ID before checking for a missed contradiction.

    Uses ONLY phrase-matched status chunks (no over-aggressive fallback). Coverage is
    tracked per (status_chunk, problem_chunk) PAIR so a shared status chunk across two
    distinct problem chunks never drops the second contradiction.
    """
    status_chunks = [
        c
        for c in chunks
        if _chunk_text_has_any(c.get("text", ""), _STATUS_CLAIM_PHRASES)
    ]
    problem_chunks = [
        c
        for c in chunks
        if _chunk_text_has_any(c.get("text", ""), _CONTRADICTION_SIGNAL_PHRASES)
    ]
    if not status_chunks or not problem_chunks:
        return []

    covered_pairs: set[tuple[str, str]] = set()
    for r in risks:
        if not r.get("is_contradiction"):
            continue
        cites = set(r.get("citations", []))
        for sc in status_chunks:
            for pc in problem_chunks:
                if sc["chunk_id"] in cites and pc["chunk_id"] in cites:
                    covered_pairs.add((sc["chunk_id"], pc["chunk_id"]))

    groups: dict[str, list[dict]] = {}
    for pc in problem_chunks:
        if all(
            (sc["chunk_id"], pc["chunk_id"]) in covered_pairs for sc in status_chunks
        ):
            continue
        ids = _TICKET_ID_PATTERN.findall(pc.get("text", "") or "")
        key = ids[0] if ids else f"__chunk__{pc['chunk_id']}"
        groups.setdefault(key, []).append(pc)

    return [(status_chunks, group) for group in groups.values()]


def _call_llm_targeted_contradiction_check(
    status_chunks: list[dict], problem_chunks: list[dict]
):
    """Forces one explicit judgment per real underlying issue, not per raw chunk pair."""
    evidence_text = _format_evidence(status_chunks + problem_chunks)
    try:
        completion = client.beta.chat.completions.parse(
            model=LLM_MODEL,
            temperature=0,
            seed=42,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Evidence -- determine ONLY whether any status-claim chunk here "
                        f"contradicts the problem chunk(s) below, per Rule 4:\n\n{evidence_text}"
                    ),
                },
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

    # Stable input ordering: makes dedup index-order comparisons insensitive to retrieval jitter.
    chunks = sorted(chunks, key=lambda c: c.get("chunk_id", ""))

    evidence_text = _format_evidence(chunks)
    logger.info("Analysing %d evidence chunk(s) for delivery risks.", len(chunks))
    parsed_response = _call_llm(evidence_text)
    risks = _parse_risks_response(parsed_response)
    risks = _expand_citations_with_ticket_corroboration(risks, chunks)

    # Drop ungrounded contradictions from the first pass so they can't reject the report.
    risks = [
        r
        for r in risks
        if not r.get("is_contradiction") or _is_grounded_contradiction(r, chunks)
    ]

    candidate_groups = _find_missed_contradiction_candidate_groups(chunks, risks)
    for status_chunks, problem_chunks in candidate_groups:
        forced = _call_llm_targeted_contradiction_check(status_chunks, problem_chunks)
        if not forced:
            continue
        forced_dict = {
            "risk": forced.risk,
            "explanation": forced.explanation,
            "citations": forced.citations,
            "impact_breakdown": forced.impact_breakdown.model_dump(),
            "confidence_tag": forced.confidence_tag,
            "is_sev1": forced.is_sev1,
            "is_contradiction": forced.is_contradiction,
            "recommendations": forced.recommendations,
        }
        # Only accept the forced contradiction if it is actually grounded in the
        # cited chunks (status claim + problem signal). This is what stops the
        # fabricated Atlas contradictions from rejecting the whole report.
        if not _is_grounded_contradiction(forced_dict, chunks):
            logger.info("Discarding ungrounded forced contradiction: %s", forced.risk)
            continue
        logger.warning(
            "First-pass extraction missed a contradiction (problem chunk(s): %s)",
            ", ".join(c["chunk_id"] for c in problem_chunks),
        )
        risks.append(forced_dict)

    logger.info("Extracted %d risk(s) before deduplication.", len(risks))
    risks = _dedupe_same_ticket_risks(risks)
    risks = _dedupe_contradiction_risks(risks, chunks)
    return risks
