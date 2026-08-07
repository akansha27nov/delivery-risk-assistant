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
        
        print(f"Pipeline Execution Status: {result['result']['status']}")
        print(f"Message / Outcome: {result['result'].get('message')}")
        print(f"Requires HITL Escalation: {result.get('requires_hitl')}")
        
        risks = result['result'].get('risks', [])
        print(f"Extracted Risks ({len(risks)}):")
        for r in risks:
            print(f"\n  - Risk Title: {r['risk']}")
            print(f"    Explanation: {r['explanation']}")
            print(f"    Cost Estimate: {r.get('cost_estimate')}")
            print(f"    Confidence Tag: {r.get('confidence_tag')}")
            print(f"    Flags -> SEV-1: {r.get('is_sev1')} | Contradiction: {r.get('is_contradiction')}")
            print(f"    Citations: {r.get('citations')}")

if __name__ == "__main__":
    run_test()