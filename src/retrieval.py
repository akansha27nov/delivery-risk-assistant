"""
Phase 3, Step 1: Retrieve the most relevant chunks for a query, scoped to
one project's Pinecone namespace. "project" is required, not optional --
there is no cross-project retrieve() call by design, so results can never
get jumbled across projects.

Reuse the approach from:
  github.com/akansha27nov/RAG-with-the-training-wheels-off
"""

from embedding import _embed, get_index


def retrieve(query: str, project: str, k: int = 8) -> list[dict]:
    """
    Embed the query, search Pinecone within the given project's namespace
    only, and reshape matches back into the
    {"source", "chunk_id", "text", "location", "project", "score"} shape
    used everywhere else in the pipeline.
    """
    index = get_index()
    query_vec = _embed([query])[0]
    result = index.query(vector=query_vec, top_k=k, include_metadata=True, namespace=project)
    return [
        {
            "chunk_id": match["id"],
            "source": match["metadata"]["source"],
            "location": match["metadata"]["location"],
            "text": match["metadata"]["text"],
            "project": project,
            "score": match["score"],
        }
        for match in result["matches"]
    ]
