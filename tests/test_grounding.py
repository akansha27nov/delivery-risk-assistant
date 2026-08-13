"""
Phase 4 evaluation layer -- automated checks against docs/ground_truth_risks.md.
 
These are integration tests: they call the real graph (Pinecone + OpenAI +
Cohere), so they need OPENAI_API_KEY, PINECONE_API_KEY, COHERE_API_KEY set
(via .env) and internet access. Run with:
    cd src
    pytest ../tests/test_grounding.py -v
"""
import os
import asyncio
import sys
from pathlib import Path
os.environ.setdefault("TELEGRAM_ALERTS_ENABLED", "false")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
 
from graph import build_graph 
 
QUESTION = "What are this week's top delivery risks?"
 
NOVA_SOURCES = {
    "nova_sprint_report.md", "nova_incident_postmortem.md", "nova_slack_thread.txt",
    "nova_retro_notes.md", "nova_exec_status_email.md",
}
ATLAS_SOURCES = {
    "sprint_report.md", "ticket_export.csv", "standup_transcript.txt", "stakeholder_email.md",
}
 
 
def _run(project: str) -> dict:
    graph = build_graph()
    final_state = asyncio.run(graph.ainvoke({"project": project, "question": QUESTION})) 
    return final_state["result"]
 
 
def test_all_citations_resolve_to_real_chunks():
    """
    No risk's citations should point to a chunk_id that wasn't actually
    part of the evidence used to answer.
    """
    for project in ["atlas", "nova"]:
        result = _run(project)
        # Allow the new HITL status
        assert result["status"] in ("ok", "rejected", "pending_hitl_approval"), (
            f"{project}: expected a definitive result, got {result['status']}"
        )
        # Only strictly enforce validity if it didn't get outright rejected
        if result["status"] in ("ok", "pending_hitl_approval"):
            for risk in result.get("risks", []):
                assert risk["valid"], (
                    f"{project}: risk '{risk['risk']}' has an invalid/fabricated "
                    f"citation: {risk['citations']}"
                )

def test_no_resolved_issue_flagged_as_current_risk():
    """
    Negative control: NOV-175 (CI flakiness) is explicitly resolved.
    """
    result = _run("nova")
    # Nova triggers HITL due to the Sev1/Contradiction logic
    assert result["status"] in ("ok", "pending_hitl_approval")
    for risk in result.get("risks", []):
        text = (risk["risk"] + " " + risk["explanation"]).lower()
        assert "flak" not in text and "nov-175" not in text, (
            f"Resolved CI flakiness issue appears to have been flagged as a "
            f"current risk: {risk['risk']}"
        )

def test_attrition_risk_if_present_is_single_sourced():
    """
    R3 (attrition signal) is single-source by design.
    """
    result = _run("atlas")
    # Atlas may reject if the contradiction risk fails context validation
    assert result["status"] in ("ok", "rejected", "pending_hitl_approval")
    for risk in result.get("risks", []):
        text = (risk["risk"] + " " + risk["explanation"]).lower()
        if any(kw in text for kw in ("burnout", "exploring other roles", "attrition", "retention")):
            assert all(cid.startswith("standup_transcript.txt") for cid in risk["citations"]), (
                f"Attrition risk cited a source other than the standup transcript: "
                f"{risk['citations']}"
            )

def test_atlas_and_nova_never_cross_contaminate():
    """
    A risk's citations for one project should never include a chunk_id
    from the other project's source files.
    """
    atlas_result = _run("atlas")
    nova_result = _run("nova")
 
    # Check citations regardless of the final routing status
    for risk in atlas_result.get("risks", []):
        for cid in risk["citations"]:
            source = cid.split("::")[0]
            assert source not in NOVA_SOURCES, f"Atlas risk cited a Nova source: {cid}"
 
    for risk in nova_result.get("risks", []):
        for cid in risk["citations"]:
            source = cid.split("::")[0]
            assert source not in ATLAS_SOURCES, f"Nova risk cited an Atlas source: {cid}"