"""
Manual end-to-end test of the FULL LangGraph state machine -- not the
individual pieces, the actual compiled graph from graph.py, exercising
both conditional branches (Enough Evidence?, Citation Missing?) on live
data. Run locally (needs OPENAI_API_KEY, PINECONE_API_KEY, COHERE_API_KEY
set via .env).

Usage:
    cd src
    python test_graph_manual.py
"""

from graph import build_graph

QUESTION = "What are this week's top delivery risks?"

graph = build_graph()

for project in ["atlas", "nova"]:
    final_state = graph.invoke({"project": project, "question": QUESTION})
    result = final_state["result"]

    print(f"=== {project} ===")
    print(f"status: {result['status']}")

    if result["status"] == "ok":
        for r in result["risks"]:
            tag = "VALID" if r["valid"] else "INVALID"
            print(f"  [{tag}] {r['risk']}")
            print(f"    {r['explanation']}")
            print(f"    citations: {r['citations']}")
    elif result["status"] == "rejected":
        print(f"  message: {result['message']}")
        for r in result["rejected_risks"]:
            print(f"  rejected: {r['risk']} (citations: {r['citations']})")
    elif result["status"] == "insufficient_evidence":
        print(f"  message: {result['message']}")
    print()
