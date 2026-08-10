# src/test_decision_tree.py
import asyncio
from graph import build_graph

async def run_test():
    app = build_graph()
    
    for project in ["atlas", "nova"]:
        print(f"\n==============================")
        print(f"=== Testing Project: {project.upper()} ===")
        print(f"==============================")
        
        state = {
            "project": project,
            "question": "What are this week's top delivery risks?"
        }
        
        # Await the async execution of the graph
        result = await app.ainvoke(state)
        
        res_container = result.get("result", result)
        status = res_container.get("status", "unknown")
        requires_hitl = result.get("requires_hitl", False)
        risks = res_container.get("risks", [])
        
        print(f"Pipeline Execution Status: {status}")
        print(f"Requires HITL Escalation: {requires_hitl}")
        print(f"Extracted Risks ({len(risks)})")

if __name__ == "__main__":
    asyncio.run(run_test())