"""
Manual end-to-end test of the reasoning layer, run locally (needs
OPENAI_API_KEY, PINECONE_API_KEY, COHERE_API_KEY set via .env).
 
Usage:
    cd src
    python test_agent_manual.py
"""
 
from agent import analyse_risks, validate_citations
from retrieval import gather_evidence
 
QUERY = "What are this week's top delivery risks?"
 
for project in ["atlas", "nova"]:
    evidence = gather_evidence(QUERY, project=project)
 
    print(f"=== {project} ===")
    print(f"  ({len(evidence)} evidence chunks gathered):")
    for c in evidence:
        print(f"    - {c['location']}")
    print()
 
    risks = analyse_risks(evidence)
    known_ids = {c["chunk_id"] for c in evidence}
    validated = validate_citations(risks, known_ids)
 
    if not validated:
        print("  (no risks returned)")
    for r in validated:
        status = "VALID" if r["valid"] else "INVALID"
        print(f"  [{status}] {r['risk']}")
        print(f"    {r['explanation']}")
        print(f"    citations: {r['citations']}")
    print()