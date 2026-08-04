"""
Phase 3, Step 2: Rerank the chunks returned by retrieval using Cohere
Rerank, so the agent reasons over the most relevant evidence first --
not just the highest cosine-similarity matches, which (as you saw in the
Pinecone sanity check) can rank a "no blockers" chunk above an actual
blocked-ticket chunk purely on surface wording overlap.

Needs COHERE_API_KEY set (see .env.example).

Reuse the approach from:
  github.com/akansha27nov/first-match-is-not-right-match
"""

import os

import cohere
from dotenv import load_dotenv

load_dotenv()

RERANK_MODEL = "rerank-v3.5"

co = cohere.Client(os.environ["COHERE_API_KEY"])


def rerank(query: str, chunks: list[dict], top_n: int = 5) -> list[dict]:
    """
    Call Cohere's rerank API on the retrieved chunks and return the top_n,
    reordered by Cohere's relevance score.

    Note: reranking improves relevance ranking, but it does not fix
    contradiction/polarity issues on its own -- a "no blockers" chunk can
    still score as relevant to a "what's blocking the launch?" query
    because it's topically on point. Catching that a chunk's claim is the
    opposite of what's being asked is the agent reasoning step's job
    (Phase 4), not this one. This step's job is just: given N candidate
    chunks, put the most genuinely relevant ones first and drop the rest.
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
    from retrieval import retrieve

    query = "Is anything blocking the launch?"
    for project in ["atlas", "nova"]:
        candidates = retrieve(query, project=project, k=8)
        top = rerank(query, candidates, top_n=5)

        print(f"=== Project: {project} ===")
        print(f"Reranked top {len(top)} of {len(candidates)} candidates for: '{query}'\n")
        for c in top:
            print(f"  [{c['location']}] rerank_score={c['rerank_score']:.3f}")
            print(f"    {c['text'][:100]}...\n")
