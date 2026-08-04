"""
Phase 3 (next step): Retrieve the most relevant chunks for a query using
the Pinecone index built in embedding.py.

Reuse the approach from:
  github.com/akansha27nov/RAG-with-the-training-wheels-off
"""

from embedding import _embed, get_index


def retrieve(query: str, k: int = 8) -> list[dict]:
    """
    Embed the query, search Pinecone for the top-k matches, and reshape
    them back into the {"source", "chunk_id", "text", "location", "score"}
    shape used everywhere else in the pipeline.
    """
    index = get_index()
    query_vec = _embed([query])[0]
    result = index.query(vector=query_vec, top_k=k, include_metadata=True)
    return [
        {
            "chunk_id": match["id"],
            "source": match["metadata"]["source"],
            "location": match["metadata"]["location"],
            "text": match["metadata"]["text"],
            "score": match["score"],
        }
        for match in result["matches"]
    ]
