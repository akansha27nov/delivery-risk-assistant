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
 
load_dotenv()
 
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
 
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
 
SYSTEM_PROMPT = """You are a delivery risk analyst for a software engineering program.
You are given evidence chunks pulled from real project artefacts (sprint reports, ticket
exports, meeting transcripts, status emails). Each chunk has a unique chunk_id.
 
Your job: identify up to 3 delivery risks this week, using ONLY the evidence provided.
 
Hard rules:
1. Every risk you state MUST cite at least one chunk_id from the evidence that directly
   supports it. If you cannot point to a specific chunk_id, do not state the risk.
2. Do not invent chunk_ids. Only use chunk_ids that appear in the evidence below.
3. A chunk that says a specific issue is CLOSED, RESOLVED, or FIXED is not a current risk.
   Do not report resolved issues as risks, even if they were serious when open.
4. Specific, dated evidence (a blocked ticket, a named deadline, a documented incident)
   outweighs a general status claim ("on track", "no blockers", "green") that names no
   specifics. If a general status claim directly CONTRADICTS specific evidence elsewhere
   (e.g. an email says "no blockers" while a ticket has been blocked for 9 days), treat the
   contradiction itself as a risk worth reporting -- not just the underlying issue -- and
   cite both the status claim and the contradicting evidence.
5. If two or more chunks from different source documents support the same risk, say so
   explicitly (e.g. "corroborated across 3 sources") and cite all of them. If only one chunk
   supports a risk, say so too (e.g. "single-source, not yet corroborated") -- never imply
   corroboration that isn't there.
6. For risks involving a named person's wellbeing, retention, or conduct: report only what
   was explicitly said, in neutral, factual language. Do not speculate about outcomes (e.g.
   don't say someone "will quit" -- say they "indicated they are exploring other roles").
7. If the evidence does not support any confident risk, return an empty risks list rather
   than forcing 3.
 
Respond with ONLY valid JSON in this exact shape, no other text:
{
  "risks": [
    {
      "risk": "short risk title",
      "explanation": "one to two sentences explaining the risk and its evidence",
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
    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Evidence:\n\n{evidence_text}"},
        ],
    )
    return response.choices[0].message.content
 
 
def _parse_risks_response(raw_text: str) -> list[dict]:
    """
    Parse and sanity-check the LLM's JSON response. Malformed JSON or an 
    unexpected shape returns an empty list rather than crashing the graph.
    """
    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return []
 
    risks = data.get("risks", [])
    if not isinstance(risks, list):
        return []
 
    parsed = []
    for r in risks:
        if not isinstance(r, dict):
            continue
        risk_text = r.get("risk")
        citations = r.get("citations", [])
        if not risk_text or not isinstance(citations, list):
            continue
        parsed.append({
            "risk": risk_text,
            "explanation": r.get("explanation", ""),
            "citations": citations,
        })
    return parsed
 
 
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
    For each risk, check every citation actually exists in known_chunk_ids
    (the chunk_ids that were actually retrieved/reranked for this query).
    Any risk with a missing/invalid citation gets marked invalid -- this
    feeds the "Citation Missing?" branch in the graph.
    """
    validated = []
    for risk in risks:
        citations = risk.get("citations", [])
        valid = len(citations) > 0 and all(cid in known_chunk_ids for cid in citations)
        validated.append({**risk, "valid": valid})
    return validated