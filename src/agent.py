"""
Phase 4: The reasoning and trust-layer core of the project.

Reuse the grounded-evidence pattern from:
  github.com/akansha27nov/Agents-that-speak-MCP-fluently
and the evaluation-of-groundedness pattern from:
  github.com/akansha27nov/Chaos-agent
"""


def analyse_risks(chunks: list[dict]) -> list[dict]:
    """
    Given reranked evidence chunks, produce up to 3 delivery risks:
      {"risk": str, "explanation": str, "citations": [chunk_id, ...]}

    Prompt design notes (this is where your EM background matters most):
      - A risk claim must name a specific chunk_id it came from. If the
        model can't point to one, it should not state the risk.
      - Corroborated risks (same risk mentioned in 2+ documents) should be
        distinguishable from single-source risks in the output — don't
        silently merge them into equal-confidence claims.
      - People/morale risks need careful phrasing: report what was said
        ("signaled they are exploring other roles"), not a prediction
        ("employee will quit").
    """
    raise NotImplementedError


def validate_citations(risks: list[dict], known_chunk_ids: set[str]) -> list[dict]:
    """
    For each risk, check every citation actually exists in known_chunk_ids.
    Any risk with a missing/invalid citation gets flagged for rejection —
    this feeds the "Citation Missing?" branch in the graph.

    Return risks annotated with a "valid" bool, e.g.:
      {"risk": ..., "citations": [...], "valid": True/False}
    """
    raise NotImplementedError
