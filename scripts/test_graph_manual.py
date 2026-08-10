# src/test_graph_manual.py
import asyncio
from graph import build_graph

QUESTION = "What are this week's top delivery risks?"

async def test_full_graph():
    graph = build_graph()

    for project in ["atlas", "nova"]:
        # Must use async invocation for async retrieval nodes
        final_state = await graph.ainvoke({"project": project, "question": QUESTION})
        result = final_state.get("result", {})

        print(f"=== Project: {project} ===")
        print(f"Status: {result.get('status')}")

        if result.get("status") == "ok":
            for r in result.get("risks", []):
                tag = "VALID" if r.get("valid") else "INVALID"
                print(f"  [{tag}] {r.get('risk')}")
                print(f"    Citations: {r.get('citations')}")
        else:
            print(f"  Message: {result.get('message')}")
        print()

if __name__ == "__main__":
    asyncio.run(test_full_graph())