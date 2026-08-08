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

        is_valid = has_valid_citation and has_impact and has_confidence_tag

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
        r["confidence_breakdown"] = {
            "citation_valid": has_valid_citation,
            "num_docs": unique_docs,
            "retrieval_quality": retrieval_quality
        }
        validated.append(r)

    return validated