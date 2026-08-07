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
from retrieval import gather_evidence
 
MIN_EVIDENCE_CHUNKS = 2
 
 
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
 
 
def retrieve_documents(state: GraphState) -> GraphState:
    evidence = gather_evidence(state["question"], project=state["project"])
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
    known_ids = {c["chunk_id"] for c in state["evidence"]}
    validated = validate_citations(state["risks"], known_ids)
    citation_missing = any(not r["valid"] for r in validated)
    return {**state, "risks": validated, "citation_missing": citation_missing}
 
 
def has_citation_missing(state: GraphState) -> str:
    return "yes" if state.get("citation_missing") else "no"
 
 
def evaluate_severity_decision_tree(state: GraphState) -> GraphState:
    """
    Deterministic Binary Decision Tree[cite: 33]:
    Rule 3: Does another source contradict this claim? -> Route to HITL[cite: 33]
    Rule 4: Is the source explicitly tagged SEV-1? -> Route to HITL[cite: 33]
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
    invalid = [r for r in state["risks"] if not r["valid"]]
    return {**state, "result": {
        "status": "rejected",
        "message": "One or more risks were rejected for lacking a valid citation or mandatory confidence tag.",
        "rejected_risks": invalid,
    }}
 
 
def route_to_hitl(state: dict) -> dict:
    """Sends a Telegram alert when a high-severity risk or status contradiction is flagged."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    project = state.get("project", "unknown")
    
    # Safely pull risks from state whether they are nested or top-level
    risks = state.get("risks", state.get("result", {}).get("risks", []))
    
    risk_summary = "\n".join(
        [f"• {r.get('risk')} (Cost: {r.get('cost_estimate', 'N/A')})" for r in risks]
    )
    
    # Use plain text (no parse_mode) to prevent Telegram 400 Bad Request errors from special characters
    message = (
        f"🚨 HITL Escalation Required\n"
        f"Project: {project.upper()}\n"
        f"Reason: High-severity risk or status contradiction detected.\n\n"
        f"Extracted Risks:\n{risk_summary}"
    )
    
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            print("Telegram HITL alert sent successfully!")
        except Exception as e:
            print(f"Error sending Telegram notification: {e}")
    else:
        print("Telegram credentials missing. Skipping notification delivery.")
        
    state["requires_hitl"] = True
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