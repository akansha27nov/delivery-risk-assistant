"""
Phase 4: LangGraph state machine with deterministic decision-tree severity routing.

    START -> Load Question -> Retrieve Docs -> Enough Evidence?
      -- No  --> Ask for More Documents ----------------------------> END
      -- Yes --> Analyse Risks -> Validate Citations -> Citation/Tag Missing?
                   -- Yes --> Reject Response ----------------------> END
                   -- No  --> Evaluate Severity -> High Severity?
                                -- Yes --> Route to HITL -----------| (Telegram Gate)
                                -- No  --> Generate Report ---------> END
"""
import os
import requests
from typing import TypedDict
from langgraph.graph import END, StateGraph
from agent import analyse_risks, validate_citations
from retrieval import gather_evidence_async
from config import (
    MIN_EVIDENCE_CHUNKS,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID
)

class GraphState(TypedDict, total=False):
    project: str
    question: str
    evidence: list[dict]
    risks: list[dict]
    citation_missing: bool
    requires_hitl: bool
    result: dict

def load_user_question(state: GraphState) -> GraphState:
    return state

# Changed to async def to await concurrent multi-angle retrieval
async def retrieve_documents(state: GraphState) -> GraphState:
    evidence = await gather_evidence_async(state["project"], state["question"])
    return {**state, "evidence": evidence}

def has_enough_evidence(state: GraphState) -> str:
    evidence = state.get("evidence", [])
    return "yes" if len(evidence) >= MIN_EVIDENCE_CHUNKS else "no"

def ask_for_more_documents(state: GraphState) -> GraphState:
    return {**state, "result": {
        "status": "insufficient_evidence",
        "message": (
            f"Not enough relevant evidence was found in the '{state['project']}' "
            "project documents to answer this confidently."
        ),
    }}

def analyse_risks_node(state: GraphState) -> GraphState:
    risks = analyse_risks(state["evidence"])
    return {**state, "risks": risks}

def validate_citations_node(state: GraphState) -> GraphState:
    # Pass the full evidence chunk list (not just chunk_ids) so
    # validate_citations() can compute a real retrieval-quality score
    # from each citation's actual rerank_score, instead of falling back
    # to a hardcoded default.
    validated = validate_citations(state["risks"], state["evidence"])
    citation_missing = any(not r["valid"] for r in validated)
    return {**state, "risks": validated, "citation_missing": citation_missing}


def has_citation_missing(state: GraphState) -> str:
    return "yes" if state.get("citation_missing") else "no"

def evaluate_severity_decision_tree(state: GraphState) -> GraphState:
    """
    Deterministic Binary Decision Tree:
    Rule 3: Does another source contradict this claim? -> Route to HITL
    Rule 4: Is the source explicitly tagged SEV-1? -> Route to HITL
    """
    valid_risks = [r for r in state.get("risks", []) if r.get("valid")]
    
    requires_hitl = False
    for r in valid_risks:
        if r.get("is_sev1") or r.get("is_contradiction"):
            requires_hitl = True
            break
            
    return {**state, "requires_hitl": requires_hitl}

def is_high_severity(state: GraphState) -> str:
    return "yes" if state.get("requires_hitl") else "no"

def reject_response(state: GraphState) -> GraphState:
    all_risks = state["risks"]
    invalid = [r for r in all_risks if not r["valid"]]

    reasons = []
    for r in invalid:
        if not r.get("context_consistent", True):
            reasons.append(f"\"{r['risk']}\" -- context mismatch: {r.get('context_mismatch_detail', '')}")
        elif not r.get("citations"):
            reasons.append(f"\"{r['risk']}\" -- no valid citation")
        else:
            reasons.append(f"\"{r['risk']}\" -- missing required confidence tag or impact breakdown")

    message = (
        f"{len(invalid)} of {len(all_risks)} risk(s) failed validation:\n"
        + "\n".join(f"- {reason}" for reason in reasons)
    )

    return {**state, "result": {
        "status": "rejected",
        "message": message,
        "risks": all_risks,  # full list (valid + invalid) so nothing is hidden from view
        "rejected_risks": invalid,
    }}

def route_to_hitl(state: dict) -> dict:
    """Sends a Telegram alert when a high-severity risk or status contradiction is flagged."""
    project = state.get("project", "unknown")
    risks = state.get("risks", state.get("result", {}).get("risks", []))
    
    risk_summary = "\n".join(
        [
            f"• {r.get('risk')} "
            f"(Business impact: {r.get('impact_breakdown', {}).get('business_impact', 'N/A')})"
            for r in risks
        ]
    )
    
    telegram_message = (
        f"🚨 HITL Escalation Required\n"
        f"Project: {project.upper()}\n"
        f"Reason: High-severity risk or status contradiction detected.\n\n"
        f"Extracted Risks:\n{risk_summary}"
    )
    
    # Track the actual outcome of the Telegram API call
    ui_message = ""
    
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": telegram_message
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            print("Telegram HITL alert sent successfully!")
            ui_message = "High-severity risk or status contradiction detected. Escalated to Telegram for human review."
        except Exception as e:
            print(f"Error sending Telegram notification: {e}")
            ui_message = "High-severity risk detected, but Telegram delivery failed (Network/API Error). Check console for details."
    else:
        print("Telegram credentials missing. Skipping notification delivery.")
        ui_message = "High-severity risk detected, but Telegram credentials are missing in the environment. Alert not sent."
        
    state["requires_hitl"] = True
    state["result"] = {
        "status": "pending_hitl_approval",
        "message": ui_message,  # Surfacing the actual delivery reality to the UI
        "risks": risks
    }
    return state

def generate_report(state: GraphState) -> GraphState:
    return {**state, "result": {
        "status": "ok",
        "project": state["project"],
        "risks": state["risks"],
    }}

def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("load_user_question", load_user_question)
    graph.add_node("retrieve_documents", retrieve_documents)
    graph.add_node("ask_for_more_documents", ask_for_more_documents)
    graph.add_node("analyse_risks", analyse_risks_node)
    graph.add_node("validate_citations", validate_citations_node)
    graph.add_node("evaluate_severity", evaluate_severity_decision_tree)
    graph.add_node("reject_response", reject_response)
    graph.add_node("route_to_hitl", route_to_hitl)
    graph.add_node("generate_report", generate_report)

    graph.set_entry_point("load_user_question")
    graph.add_edge("load_user_question", "retrieve_documents")
    graph.add_conditional_edges(
        "retrieve_documents",
        has_enough_evidence,
        {"yes": "analyse_risks", "no": "ask_for_more_documents"},
    )
    graph.add_edge("ask_for_more_documents", END)
    graph.add_edge("analyse_risks", "validate_citations")
    
    # Decision Tree Edge 1: Validation
    graph.add_conditional_edges(
        "validate_citations",
        has_citation_missing,
        {"yes": "reject_response", "no": "evaluate_severity"},
    )
    graph.add_edge("reject_response", END)
    
    # Decision Tree Edge 2: Severity Routing
    graph.add_conditional_edges(
        "evaluate_severity",
        is_high_severity,
        {"yes": "route_to_hitl", "no": "generate_report"},
    )
    graph.add_edge("route_to_hitl", END)
    graph.add_edge("generate_report", END)

    return graph.compile()

def export_workflow_diagrams(png_output_path: str = "docs/workflow_diagram.png") -> str:
    """
    Programmatically generates the Mermaid syntax and renders a pretty PNG 
    architecture diagram directly from the compiled LangGraph workflow.
    """
    # Assuming your compiled graph object is named 'app' or returned by a builder function
    compiled_graph = build_graph()  # Replace with your actual compilation variable/function if different
    graph_runnable = compiled_graph.get_graph()
    
    # 1. Programmatically fetch the raw Mermaid syntax string
    mermaid_syntax = graph_runnable.draw_mermaid()
    
    # 2. Programmatically generate and export a pretty PNG image via code
    try:
        graph_runnable.draw_mermaid_png(
            output_file_path=png_output_path,
            background_color="white",
            padding=15
        )
        print(f"Successfully generated workflow diagram PNG at: {png_output_path}")
    except Exception as e:
        print(f"PNG generation skipped or failed (network/API required for mermaid.ink): {e}")
        
    return mermaid_syntax

if __name__ == "__main__":
    print("=== Programmatically Exporting LangGraph Workflow ===")
    code = export_workflow_diagrams()
    print("\nGenerated Mermaid Code:")
    print(code)