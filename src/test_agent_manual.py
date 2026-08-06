"""
Manual end-to-end test of the reasoning layer, run locally (needs
OPENAI_API_KEY, PINECONE_API_KEY, COHERE_API_KEY set via .env).

Usage:
    cd src
    python test_agent_manual.py
"""

from agent import analyse_risks, validate_citations
from rerank import rerank
from retrieval import retrieve

QUERY = "What are this week's top delivery risks?"

for project in ["atlas", "nova"]:
    candidates = retrieve(QUERY, project=project, k=8)
    evidence = rerank(QUERY, candidates, top_n=5)
    risks = analyse_risks(evidence)
    known_ids = {c["chunk_id"] for c in evidence}
    validated = validate_citations(risks, known_ids)

    print(f"=== {project} ===")
    if not validated:
        print("  (no risks returned)")
    for r in validated:
        status = "VALID" if r["valid"] else "INVALID"
        print(f"  [{status}] {r['risk']}")
        print(f"    {r['explanation']}")
        print(f"    citations: {r['citations']}")
    print()
