"""
Diagnostic: call graph.py's own node functions directly (not through the
compiled graph.invoke()) to isolate whether the "insufficient_evidence"
result is coming from bad evidence, or from a bug in how the graph reads
that evidence.

Usage:
    cd src
    python test_graph_diagnostic.py
"""

from graph import MIN_RERANK_SCORE, has_enough_evidence, retrieve_documents

for project in ["atlas", "nova"]:
    state = {"project": project, "question": "What are this week's top delivery risks?"}
    state = retrieve_documents(state)
    evidence = state.get("evidence", [])

    print(f"=== {project} ===")
    print(f"MIN_RERANK_SCORE threshold: {MIN_RERANK_SCORE}")
    print(f"evidence count: {len(evidence)}")
    if evidence:
        print(f"top chunk location: {evidence[0].get('location')}")
        print(f"top chunk keys: {list(evidence[0].keys())}")
        print(f"top chunk rerank_score: {evidence[0].get('rerank_score')!r}")
    print(f"has_enough_evidence(state) routes to: {has_enough_evidence(state)}")
    print()
