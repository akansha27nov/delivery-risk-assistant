"""
Rerank the chunks returned by retrieval using Cohere Rerank, so the agent reasons 
over the most relevant evidence first - not just the highest cosine-similarity matches.
"""
 
import os
 
import cohere
from dotenv import load_dotenv
from retrieval import retrieve
 
load_dotenv()
 
RERANK_MODEL = "rerank-v3.5"
 
co = cohere.Client(os.environ["COHERE_API_KEY"])
 
 
def rerank(query: str, chunks: list[dict], top_n: int = 5) -> list[dict]:
    """
    Call Cohere's rerank API on the retrieved chunks and return the top_n,
    reordered by Cohere's relevance score.
    """
    if not chunks:
        return []
 
    response = co.rerank(
        model=RERANK_MODEL,
        query=query,
        documents=[c["text"] for c in chunks],
        top_n=min(top_n, len(chunks)),
    )
 
    reranked = []
    for result in response.results:
        chunk = dict(chunks[result.index])  # copy, don't mutate original
        chunk["rerank_score"] = result.relevance_score
        reranked.append(chunk)
    return reranked
 
 
if __name__ == "__main__":
    query = "Is anything blocking the launch?"
    candidates = retrieve(query, k=8)
    top = rerank(query, candidates, top_n=5)
 
    print(f"Reranked top {len(top)} of {len(candidates)} candidates for: '{query}'\n")
    for c in top:
        print(f"  [{c['location']}] rerank_score={c['rerank_score']:.3f}")
        print(f"    {c['text'][:100]}...\n")