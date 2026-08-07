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
 
import json
import os
 
from dotenv import load_dotenv
from openai import OpenAI
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
10. COST/IMPACT ESTIMATION & CONFIDENCE TAGS: For every risk, provide a "cost_estimate" describing 
    the financial cost, schedule delay, or resource impact. Assign a mandatory "confidence_tag". 
    It must be EXACTLY one of these two strings: set it to "estimated_from_source_data" ONLY if 
    a specific dollar figure, ticket count, or exact metric exists in the cited evidence chunks; 
    otherwise set it to "directional_estimate".
11. SEVERITY METADATA FLAGS: Include is_sev1: true if the risk involves an active SEV-1 incident, 
    P0 bug, or an open/unassigned postmortem remediation ticket from a SEV-1 outage; otherwise false."

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
      "cost_estimate": "description of delay, dollar impact, or operational cost",
      "confidence_tag": "estimated_from_source_data OR directional_estimate",
      "is_contradiction": true,
      "is_sev1": false,
      "citations": ["chunk_id_1", "chunk_id_2"]
    }
  ]
}
"""
 
 
def _format_evidence(chunks: list[dict]) -> str:
    """Pure formatting, no LLM call -- testable on its own."""
    blocks = []
    for c in chunks:
        blocks.append(f"chunk_id: {c['chunk_id']}\nsource: {c['location']}\ntext: {c['text']}")
    return "\n---\n".join(blocks)
 
 
def _call_llm(evidence_text: str) -> str:
    """The one part of this file that needs OPENAI_API_KEY + internet."""
    response = client.chat.completions.create(
        model=LLM_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Evidence:\n\n{evidence_text}"},
        ],
    )
    return response.choices[0].message.content
 
 
def _parse_risks_response(raw_text: str) -> list[dict]:
    """Parse and sanity-check the LLM's JSON response structure."""
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return []
 
    risks = data.get("risks", [])
    if not isinstance(risks, list):
        return []
 
    parsed_risks = []
    for risk in data.get("risks", []):
        # 1. STRICT CONFIDENCE TAG
        # If it's missing or an hallucinated value, set to None so validation catches it
        raw_tag = risk.get("confidence_tag")
        valid_tags = ["directional_estimate", "estimated_from_source_data"]
        confidence_tag = raw_tag if raw_tag in valid_tags else None
        
        # 2. STRICT COST ESTIMATE
        # If missing or blank, set to None so validation catches it
        raw_cost = risk.get("cost_estimate", "").strip()
        cost_estimate = raw_cost if raw_cost else None
        
        parsed_risks.append({
            "risk": risk.get("risk", "Unknown Risk"),
            "explanation": risk.get("explanation", ""),
            "citations": risk.get("citations", []),
            "cost_estimate": cost_estimate,       # Now strictly None if missing
            "confidence_tag": confidence_tag,     # Now strictly None if invalid
            "is_sev1": risk.get("is_sev1", False),
            "is_contradiction": risk.get("is_contradiction", False)
        })
        
    return parsed_risks
 
 
def analyse_risks(chunks: list[dict]) -> list[dict]:
    """
    Given reranked evidence chunks, ask the LLM to identify up to 3
    delivery risks, each grounded in at least one real chunk_id.
    """
    if not chunks:
        return []
    evidence_text = _format_evidence(chunks)
    raw = _call_llm(evidence_text)
    return _parse_risks_response(raw)
 
 
def validate_citations(risks: list[dict], known_chunk_ids: set[str]) -> list[dict]:
    """
    Validates both citations and structural requirements (cost estimate & confidence tag).
    Any risk lacking a valid citation or missing a confidence tag gets marked invalid.
    """
    validated = []
    for r in risks:
        # Check citations
        valid_cites = [c for c in r.get("citations", []) if c in known_ids]
        has_valid_citation = len(valid_cites) > 0
        
        # Check structural requirements
        has_cost = r.get("cost_estimate") is not None
        has_confidence = r.get("confidence_tag") is not None
        
        # Fail the risk if ANY requirement is missing
        is_valid = has_valid_citation and has_cost and has_confidence
        
        r["valid"] = is_valid
        r["citations"] = valid_cites
        validated.append(r)
    return validated