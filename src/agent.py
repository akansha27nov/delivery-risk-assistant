"""
The reasoning and trust-layer core of the project.
 
analyse_risks() is now the real implementation -- an LLM call grounded in
the evidence chunks retrieved/reranked upstream. It's split into three
parts so the parts that don't need the network can be tested for real:
 
  _format_evidence()       -- pure Python, testable
  _call_llm()               -- needs OPENAI_API_KEY + internet
  _parse_risks_response()  -- pure Python, testable
 
validate_citations() is unchanged -- still real, still the
final safety net regardless of how good or bad the LLM's own citation
discipline turns out to be.
"""
 
from typing import List, Optional
import re
from openai import OpenAI
from pydantic import BaseModel, Field, field_validator
from config import OPENAI_API_KEY, LLM_MODEL

VALID_CONFIDENCE_TAGS = {"estimated_from_source_data", "directional_estimate"}
client = OpenAI(api_key=OPENAI_API_KEY)
 
SYSTEM_PROMPT = """You are a delivery risk analyst for a software engineering programme.
You are given evidence chunks pulled from real project artefacts (sprint reports, ticket
exports, meeting transcripts, status emails). Each chunk has a unique chunk_id.
 
Your job: identify up to 3 delivery risks this week, using ONLY the evidence provided.
 
Hard rules:
1. Every risk you state MUST cite at least one chunk_id from the evidence that directly
   supports it. If you cannot point to a specific chunk_id, do not state the risk.
2. Do not invent chunk_ids. Only use chunk_ids that appear in the evidence below.
3. A chunk that says a specific issue is CLOSED, RESOLVED, or FIXED is not a current risk.
   Do not report resolved issues as risks, even if they were serious when open.
4. REQUIRED CHECK, every time: scan the evidence for any general status claim -- phrases like 
   "on track", "green", "no blockers", "all good", "no issues to flag". For each one you find, 
   actively check whether any OTHER chunk in the evidence describes a specific, dated problem 
   (a blocked ticket, an open incident remediation, a missed deadline) that contradicts it. 
   If you find such a contradiction, you MUST report it as one of your top risks -- ranked above 
   softer or less specific risks -- citing BOTH the status claim chunk and the chunk(s) it 
   contradicts. Do not silently resolve the contradiction in the status claim's favor, and do 
   not just report the underlying issue without naming the contradiction itself as the risk. 
   If a contradiction exists, you MUST set "is_contradiction": true in your output. Otherwise, 
   set it to false.
5. REQUIRED CHECK, every time: scan the evidence for new work, tickets, or requests added
   to a sprint/project OUTSIDE of original planning -- phrases like "added mid-sprint",
   "outside of planning", "wasn't part of the original plan", or a stakeholder asking for
   something on short notice without a corresponding deadline or scope trade-off. This is
   "scope creep" -- treat it as a real, reportable delivery risk in its own right, not just
   background context for another risk. It competes for a top-3 slot like any other risk; do
   not let it get silently absorbed into a different risk's citation list.
6. If two or more chunks from different source documents support the same risk, say so
   explicitly (e.g. "corroborated across 3 sources") and cite all of them. If only one chunk
   supports a risk, say so too (e.g. "single-source, not yet corroborated") -- never imply
   corroboration that isn't there.
7. For risks involving a named person's wellbeing, retention, or conduct: report only what
   was explicitly said, in neutral, factual language. Do not speculate about outcomes (e.g.
   don't say someone "will quit" -- say they "indicated they are exploring other roles").
8. If the evidence does not support any confident risk, return an empty risks list rather
   than forcing 3.
9. Each of your risks must represent a genuinely distinct underlying issue. Do not split one
   issue across two risk entries, and do not pad a risk's citations with chunks that don't
   directly support that specific risk's claim just because they're topically related.
   In particular: a status-contradiction risk (rule 4) and the underlying problem it
   contradicts are ONE risk, not two. If a status claim says "on track" while a specific
   deadline or blocker is actually at risk, report that as a single risk that names both the
   contradiction and the underlying deadline/blocker -- never as one risk about "the
   contradiction" and a separate risk about "the deadline," even though they share evidence.
10. IMPACT BREAKDOWN & CONFIDENCE TAGS: For every risk, provide a structured "impact_breakdown" 
    detailing delivery, customer, business, and team impacts. Assign a mandatory "confidence_tag"...
11. SEVERITY METADATA FLAGS: Include is_sev1: true if the risk involves an active SEV-1 incident, 
    P0 bug, or an open/unassigned postmortem remediation ticket from a SEV-1 outage; otherwise false."
12. RECOMMENDATIONS RULE: For every identified risk, you must provide exactly 2-3 actionable recommendations 
    in a list format. These MUST be strictly derived from the provided evidence. 
    Do not hallucinate external solutions.
    
Worked example of rule 4 (contradiction detection):
 
Evidence includes:
  chunk_id: status_update::1
  text: "Status: green. No blockers to flag this week."
 
  chunk_id: incident_report::1
  text: "SEV-1 payment defect found on 2026-06-01. Remediation ticket is unassigned with no
  target date."
 
Correct output includes a risk like:
{
  "risk": "Status report contradicts open incident evidence",
  "explanation": "The status update claims no blockers, but an unassigned SEV-1 remediation ticket with no target date is still open. The status report does not reflect this.",
  "cost_estimate": "Delayed incident remediation with potential outage/revenue impact",
  "confidence_tag": "directional_estimate",
  "is_contradiction": true,
  "is_sev1": true,
  "citations": ["status_update::1", "incident_report::1"]
}
 
Worked example of rule 5 (scope creep detection):
 
Evidence includes:
  chunk_id: ticket_export::1
  text: "ticket_id: XYZ-99; summary: Add new banner; status: In Progress; blocked_reason:
  Added mid-sprint outside original planning scope"
 
Correct output includes a risk like:
{
  "risk": "Uncontrolled mid-sprint scope addition",
  "explanation": "New work (XYZ-99) was added to the sprint outside of original planning, with no corresponding timeline adjustment or scope trade-off.",
  "cost_estimate": "Engineering capacity deflection from planned sprint commitments",
  "confidence_tag": "directional_estimate",
  "is_contradiction": false,
  "is_sev1": false,
  "citations": ["ticket_export::1"]
}
 
IMPORTANT: the two worked examples above illustrate the PATTERN to look for -- they are not
real evidence and their chunk_ids ("status_update::1", "incident_report::1", "ticket_export::1")
do not exist in your actual evidence set below. Never cite them. Never reuse their exact risk
titles or explanation wording. Every risk title and explanation you output must be written
fresh, from the actual evidence chunks you were given, describing what THAT evidence actually
says.
 
Respond with ONLY valid JSON in this exact shape, no other text:
{
  "risks": [
    {
      "risk": "short risk title",
      "explanation": "one to two sentences explaining the risk and its evidence",
      "impact_breakdown": {
        "delivery_impact": "description of schedule delay or milestone impact",
        "customer_impact": "description of end-user or partner impact",
        "business_impact": "description of revenue or strategic impact",
        "team_impact": "description of engineering capacity or morale impact"
      },
      "confidence_tag": "estimated_from_source_data OR directional_estimate",
      "is_contradiction": true,
      "is_sev1": false,
      "citations": ["chunk_id_1", "chunk_id_2"],
      "recommendations": ["Actionable step 1 based on evidence", "Actionable step 2 based on evidence"]
    }
  ]
}
"""
 
# ==========================================
# 🛡️ Pydantic Schemas for Structured Output
# ==========================================

class ImpactBreakdown(BaseModel):
    delivery_impact: str = Field(description="Impact on project timelines, milestones, or deliverables.")
    customer_impact: str = Field(description="Impact on end-users, stakeholders, or external partners.")
    business_impact: str = Field(description="Impact on revenue, compliance, or strategic business goals.")
    team_impact: str = Field(description="Impact on engineering capacity, morale, or workload.")
    
class RiskItem(BaseModel):
    risk: str = Field(description="Concise title or summary of the delivery risk.")
    explanation: str = Field(description="Detailed explanation of why this is a risk based on evidence.")
    citations: List[str] = Field(description="List of exact chunk IDs supporting this claim.")
    impact_breakdown: ImpactBreakdown = Field(description="Structured breakdown of the risk's impact.")
    confidence_tag: Optional[str] = Field(default=None, description="Must be 'estimated_from_source_data' or 'directional_estimate'.")
    is_sev1: bool = Field(default=False, description="True if explicitly tagged SEV-1 or critical financial/customer impact.")
    is_contradiction: bool = Field(default=False, description="True if an official status report contradicts underlying tickets/Slack threads.")
    recommendations: list[str] = Field(
        description="2-3 actionable recommendations to mitigate the risk, based ONLY on the retrieved evidence."
    )
    
    @field_validator("confidence_tag", mode="before")
    @classmethod
    def validate_confidence_tag(cls, v):
        if v not in VALID_CONFIDENCE_TAGS:
            return None
        return v

class RiskExtractionResponse(BaseModel):
    risks: List[RiskItem] = Field(description="List of extracted delivery risks meeting criteria.")


def _format_evidence(chunks: list[dict]) -> str:
    """Pure formatting, no LLM call -- testable on its own."""
    blocks = []
    for c in chunks:
        blocks.append(f"chunk_id: {c['chunk_id']}\nsource: {c['location']}\ntext: {c['text']}")
    return "\n---\n".join(blocks)
 
 
def _call_llm(evidence_text: str) -> Optional[RiskExtractionResponse]:
    """Calls OpenAI using structured outputs with Pydantic schema enforcement."""
    try:
        completion = client.beta.chat.completions.parse(
            model=LLM_MODEL,
            temperature=0,
            seed=42,  # best-effort reproducibility: OpenAI's API is not perfectly
                      # deterministic even at temperature=0 (batching/floating-point
                      # effects across separate calls) -- a fixed seed substantially
                      # reduces run-to-run variance in which/how-many risks get
                      # extracted for identical input evidence. Not a hard guarantee;
                      # see response.system_fingerprint if you need to detect when
                      # variance is caused by an OpenAI-side model update instead.
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Evidence:\n\n{evidence_text}"},
            ],
            response_format=RiskExtractionResponse,
        )
        return completion.choices[0].message.parsed
    except Exception as e:
        print(f"OpenAI structured parsing error: {e}")
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
 
 
def analyse_risks(chunks: list[dict]) -> list[dict]:
    """
    Given reranked evidence chunks, ask the LLM to identify up to 3
    delivery risks, each grounded in at least one real chunk_id,
    validated via Pydantic structured outputs.
    """
    if not chunks:
        return []
    evidence_text = _format_evidence(chunks)
    parsed_response = _call_llm(evidence_text)
    return _parse_risks_response(parsed_response)
 
 
_ENTITY_ID_PATTERN = re.compile(r'\b([A-Z]{2,8})-\d+\b')


def _extract_entity_prefixes(text: str) -> set:
    """
    Pulls ticket-style identifier prefixes (e.g. 'ATL' from 'ATL-142',
    'ORION' from 'ORION-84') out of a chunk's text. This is a cheap,
    deterministic signal for whether two cited chunks are actually
    describing the same team/system -- not just coincidentally similar
    wording. Two chunks both mentioning "QA capacity" can still be about
    two unrelated teams; two chunks both mentioning "ATL-142" are almost
    certainly about the same one.
    """
    return {m.upper() for m in _ENTITY_ID_PATTERN.findall(text or "")}


def _check_context_consistency(valid_cites: list, evidence_map: dict):
    """
    Before a risk is accepted, check whether its cited chunks describe
    the SAME project context -- not just the same Pinecone namespace.
    A risk can pass citation validation (every citation is real,
    traceable text) while still being misleading, if it stitches
    together unrelated facts from different teams/systems that happen to
    share a namespace -- e.g. a document about an unrelated team gets
    uploaded into this project, and the model cites one real fact from
    each as if they corroborate a single claim.

    This is a deterministic heuristic scoped to what's cheaply checkable:
    it flags a mismatch only when cited chunks contain DIFFERENT,
    non-overlapping entity-ID prefixes (e.g. ATL-* vs ORION-*). It cannot
    catch context mismatches in prose with no ticket-style identifiers --
    that would need a semantic/LLM-based check, a known v2 extension, not
    a gap this heuristic claims to close.

    Returns (is_consistent: bool, detail: str).
    """
    prefix_groups = {}
    for cid in valid_cites:
        prefixes = _extract_entity_prefixes(evidence_map.get(cid, {}).get("text", ""))
        if prefixes:
            prefix_groups[cid] = prefixes

    if len(prefix_groups) < 2:
        return True, ""  # not enough chunks carrying identifiers to compare

    common = set.intersection(*prefix_groups.values())
    if common:
        return True, ""

    conflict_desc = "; ".join(f"{cid} mentions {sorted(p)}" for cid, p in prefix_groups.items())
    return False, f"Citations reference unrelated entity groups with no overlap -- {conflict_desc}"


def validate_citations(risks: list[dict], evidence) -> list[dict]:
    """
    Validates citations, impact breakdown, and computes transparent Evidence Confidence
    using objective retrieval and validation metrics.

    Retrieval quality is computed as a PERCENTILE RANK within the actual evidence
    pool gathered for this query, not a fixed absolute score threshold. Cohere's
    rerank score is not a calibrated 0-1 confidence value -- real scores observed
    across this corpus range roughly 0.01-0.45, so a fixed "High >= 0.8" cutoff
    would label every single risk "Low" regardless of whether it's actually the
    strongest or weakest evidence retrieved. Percentile rank answers a question
    the raw score can't: was this risk's evidence more or less relevant than the
    rest of what was retrieved for this same query?
    """
    evidence_map = {}
    all_scores = []
    if evidence and isinstance(next(iter(evidence), None), dict):
        evidence_map = {c.get("chunk_id"): c for c in evidence}
        known_ids = set(evidence_map.keys())
        all_scores = [
            c.get("rerank_score", c.get("score", 0.0)) for c in evidence
        ]
    else:
        known_ids = set(evidence) if evidence else set()

    validated = []
    for r in risks:
        valid_cites = [c for c in r.get("citations", []) if c in known_ids]
        has_valid_citation = len(valid_cites) > 0

        has_impact = r.get("impact_breakdown") is not None
        has_confidence_tag = r.get("confidence_tag") is not None

        # Context consistency: do the cited chunks actually describe the
        # same project/system, not just live in the same namespace? A
        # risk citing two chunks about two unrelated teams is NOT a
        # valid corroborated finding, even if both citations individually
        # point to real text -- this is checked before the risk is
        # allowed to pass validation at all.
        context_consistent, context_mismatch_detail = True, ""
        if evidence_map and has_valid_citation:
            context_consistent, context_mismatch_detail = _check_context_consistency(
                valid_cites, evidence_map
            )

        is_valid = (
            has_valid_citation and has_impact and has_confidence_tag and context_consistent
        )

        # ==========================================
        # EVIDENCE CONFIDENCE HEURISTIC
        # ==========================================
        # Base weight: 20%
        base_score = 20.0

        # 1. Citation Validation: 30%
        citation_score = 30.0 if has_valid_citation else 0.0

        # 2. Number of Supporting Documents: 25% max (scaled by count)
        # Dedupe by source file, not by chunk -- two citations from the
        # same document is one source of corroboration, not two.
        num_citations = len(valid_cites)
        unique_docs = len({c.split("::")[0] for c in valid_cites})
        supporting_docs_score = min(unique_docs * 8.33, 25.0)

        # 3. Retrieval quality, as a percentile rank within THIS query's
        # evidence pool: 25% max
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

        # A context mismatch means the "supporting evidence" isn't really
        # supporting anything coherent -- cap confidence hard regardless
        # of how good the individual citation scores looked in isolation.
        # This is deliberately a cap, not a proportional penalty: a
        # stitched-together claim from unrelated sources shouldn't be
        # able to buy back confidence just by citing more of them.
        if not context_consistent:
            evidence_confidence = min(evidence_confidence, 20)

        # Human-readable retrieval quality label, based on percentile rank
        # (top third / middle third / bottom third of THIS query's pool),
        # not an absolute score comparison.
        if percentile >= 0.66:
            retrieval_quality = "High"
        elif percentile >= 0.33:
            retrieval_quality = "Medium"
        else:
            retrieval_quality = "Low"
        # ==========================================

        r["valid"] = is_valid
        r["citations"] = valid_cites
        r["evidence_confidence"] = evidence_confidence
        r["context_consistent"] = context_consistent
        r["context_mismatch_detail"] = context_mismatch_detail
        r["confidence_breakdown"] = {
            "citation_valid": has_valid_citation,
            "num_docs": unique_docs,
            "retrieval_quality": retrieval_quality,
            "context_consistent": context_consistent,
        }
        validated.append(r)

    return validated