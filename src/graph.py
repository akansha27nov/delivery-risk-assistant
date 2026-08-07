"""
Phase 4: LangGraph state machine.
 
    START -> Load User Question -> Retrieve Documents -> Enough Evidence?
      -- No  --> Ask for More Documents --> END
      -- Yes --> Analyse Risks -> Validate Citations -> Citation Missing?
                   -- Yes --> Reject Response --------------------> END
                   -- No  --> Generate Report ----------------------> END
 
"Retrieve Documents" folds retrieval + rerank into one node (rerank is an
implementation detail of "getting good evidence", not a separate decision
point in the user-facing flow).
"""
 
from typing import TypedDict
 
from langgraph.graph import END, StateGraph
 
from agent import analyse_risks, validate_citations
from retrieval import gather_evidence
 
MIN_RERANK_SCORE = 0.05  # heuristic threshold for "enough evidence" -- tune in Step 4.2
 
 
class GraphState(TypedDict, total=False):
    project: str
    question: str
    evidence: list[dict]
    risks: list[dict]
    citation_missing: bool
    result: dict
 
 
def load_user_question(state: GraphState) -> GraphState:
    # Pass-through today; placeholder for future multi-turn clarification.
    return state
 
 
def retrieve_documents(state: GraphState) -> GraphState:
    evidence = gather_evidence(state["question"], project=state["project"])
    return {**state, "evidence": evidence}
 
 
def has_enough_evidence(state: GraphState) -> str:
    evidence = state.get("evidence", [])
    if evidence and evidence[0].get("rerank_score", 0) >= MIN_RERANK_SCORE:
        return "yes"
    return "no"
 
 
def ask_for_more_documents(state: GraphState) -> GraphState:
    return {**state, "result": {
        "status": "insufficient_evidence",
        "message": (
            f"Not enough relevant evidence was found in the '{state['project']}' "
            "project documents to answer this confidently. Try uploading more "
            "recent sprint reports, tickets, or meeting transcripts."
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
 
 
def reject_response(state: GraphState) -> GraphState:
    invalid = [r for r in state["risks"] if not r["valid"]]
    return {**state, "result": {
        "status": "rejected",
        "message": "One or more risks were rejected for lacking a valid citation.",
        "rejected_risks": invalid,
    }}
 
 
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
    graph.add_node("reject_response", reject_response)
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
    graph.add_conditional_edges(
        "validate_citations",
        has_citation_missing,
        {"yes": "reject_response", "no": "generate_report"},
    )
    graph.add_edge("reject_response", END)
    graph.add_edge("generate_report", END)
 
    return graph.compile()