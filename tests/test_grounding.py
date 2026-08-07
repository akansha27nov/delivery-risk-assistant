"""
Phase 4 evaluation layer -- automated checks against docs/ground_truth_risks.md.
 
These are integration tests: they call the real graph (Pinecone + OpenAI +
Cohere), so they need OPENAI_API_KEY, PINECONE_API_KEY, COHERE_API_KEY set
(via .env) and internet access. Run with:
    cd src
    pytest ../tests/test_grounding.py -v
"""
 
import sys
from pathlib import Path
 
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
    final_state = graph.invoke({"project": project, "question": QUESTION})
    return final_state["result"]
 
 
def test_all_citations_resolve_to_real_chunks():
    """
    No risk's citations should point to a chunk_id that wasn't actually
    part of the evidence used to answer -- the core "no hallucinated
    risks" guarantee the whole project is built around.
    """
    for project in ["atlas", "nova"]:
        result = _run(project)
        assert result["status"] in ("ok", "rejected"), (
            f"{project}: expected a definitive result, got {result['status']}"
        )
        if result["status"] == "ok":
            for risk in result["risks"]:
                assert risk["valid"], (
                    f"{project}: risk '{risk['risk']}' has an invalid/fabricated "
                    f"citation: {risk['citations']}"
                )
 
 
def test_no_resolved_issue_flagged_as_current_risk():
    """
    Negative control: NOV-175 (CI flakiness) is explicitly resolved in
    nova_sprint_report.md and nova_retro_notes.md. It must never be
    reported as a current risk.
    """
    result = _run("nova")
    assert result["status"] == "ok"
    for risk in result["risks"]:
        text = (risk["risk"] + " " + risk["explanation"]).lower()
        assert "flak" not in text and "nov-175" not in text, (
            f"Resolved CI flakiness issue appears to have been flagged as a "
            f"current risk: {risk['risk']}"
        )
 
 
def test_attrition_risk_if_present_is_single_sourced():
    """
    R3 (attrition signal) is single-source by design -- it should only
    ever be cited from standup_transcript.txt. The model isn't guaranteed
    to surface it in the top 3 (it's the softest risk, competing against
    harder delivery risks under a fixed 3-slot cap), so this only asserts
    something IF the risk shows up, rather than requiring it to appear.
    """
    result = _run("atlas")
    assert result["status"] == "ok"
    for risk in result["risks"]:
        text = (risk["risk"] + " " + risk["explanation"]).lower()
        if any(kw in text for kw in ("burnout", "exploring other roles", "attrition", "retention")):
            assert all(cid.startswith("standup_transcript.txt") for cid in risk["citations"]), (
                f"Attrition risk cited a source other than the standup transcript: "
                f"{risk['citations']}"
            )
 
 
def test_atlas_and_nova_never_cross_contaminate():
    """
    A risk's citations for one project should never include a chunk_id
    from the other project's source files. Namespaces are supposed to
    guarantee this structurally -- this test verifies it holds at the
    actual output level too.
    """
    atlas_result = _run("atlas")
    nova_result = _run("nova")
 
    if atlas_result["status"] == "ok":
        for risk in atlas_result["risks"]:
            for cid in risk["citations"]:
                source = cid.split("::")[0]
                assert source not in NOVA_SOURCES, f"Atlas risk cited a Nova source: {cid}"
 
    if nova_result["status"] == "ok":
        for risk in nova_result["risks"]:
            for cid in risk["citations"]:
                source = cid.split("::")[0]
                assert source not in ATLAS_SOURCES, f"Nova risk cited an Atlas source: {cid}"