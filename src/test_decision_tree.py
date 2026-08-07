# src/test_decision_tree.py
from graph import build_graph

def run_test():
    app = build_graph()
    
    for project in ["atlas", "nova"]:
        print(f"\n==============================")
        print(f"=== Testing Project: {project.upper()} ===")
        print(f"==============================")
        
        state = {
            "project": project,
            "question": "What are this week's top delivery risks?"
        }
        
        result = app.invoke(state)
        
        # Handle state keys flexibly (checking both root level and nested 'result' dict)
        res_container = result.get("result", result)
        
        status = res_container.get("status", "unknown")
        message = res_container.get("message", "No message provided")
        requires_hitl = result.get("requires_hitl", False)
        risks = res_container.get("risks", [])
        
        print(f"Pipeline Execution Status: {status}")
        print(f"Message / Outcome: {message}")
        print(f"Requires HITL Escalation: {requires_hitl}")
        print(f"Extracted Risks ({len(risks)}):")
        
        for r in risks:
            print(f"\n  - Risk Title: {r.get('risk')}")
            print(f"    Explanation: {r.get('explanation')}")
            print(f"    Cost Estimate: {r.get('cost_estimate')}")
            print(f"    Confidence Tag: {r.get('confidence_tag')}")
            print(f"    Flags -> SEV-1: {r.get('is_sev1')} | Contradiction: {r.get('is_contradiction')}")
            print(f"    Citations: {r.get('citations')}")

if __name__ == "__main__":
    run_test()