"""
Phase 2, Step 3: Embed chunks (OpenAI) and store them in Pinecone.

Needs OPENAI_API_KEY and PINECONE_API_KEY set (see .env.example) and
internet access to both APIs -> run this locally, not in a
network-restricted sandbox.

Run directly to (re)build the Pinecone index from the current data/ corpus:
    python src/embedding.py
"""

import os

from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

load_dotenv()

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536  # dimension for text-embedding-3-small
INDEX_NAME = os.environ.get("PINECONE_INDEX_NAME", "delivery-risk-assistant")

openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
pc = Pinecone(api_key=os.environ["PINECONE_API_KEY"])


def _embed(texts: list[str]) -> list[list[float]]:
    response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    return [d.embedding for d in response.data]


def _ensure_index():
    existing = [idx["name"] for idx in pc.list_indexes()]
    if INDEX_NAME not in existing:
        pc.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
    return pc.Index(INDEX_NAME)


def build_vector_store(chunks: list[dict], batch_size: int = 50):
    """
    Embed every chunk via OpenAI and upsert into Pinecone. Chunk text and
    citation metadata (source, location) are stored as Pinecone metadata
    on each vector, so a retrieved match carries its own citation with it
    -- no separate lookup needed later.

    Deletes and re-upserts on every run so re-running after editing data/
    doesn't leave stale or duplicate vectors behind.
    """
    index = _ensure_index()
    try:
        index.delete(delete_all=True)
    except Exception as e:
        if "404" not in str(e) and "Namespace not found" not in str(e):
            raise

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        vectors = _embed([c["text"] for c in batch])
        index.upsert(vectors=[
            {
                "id": c["chunk_id"],
                "values": vec,
                "metadata": {
                    "source": c["source"],
                    "location": c["location"],
                    "text": c["text"],
                },
            }
            for c, vec in zip(batch, vectors)
        ])
    return index


def get_index():
    """Reconnect to an already-built Pinecone index (used by retrieval.py)."""
    return pc.Index(INDEX_NAME)


if __name__ == "__main__":
    from chunking import chunk_documents
    from ingestion import load_documents

    docs = load_documents()
    chunks = chunk_documents(docs)
    index = build_vector_store(chunks)

    stats = index.describe_index_stats()
    print(f"Embedded and stored {stats['total_vector_count']} chunks "
          f"in Pinecone index '{INDEX_NAME}'\n")

    # Sanity check
    query_vec = _embed(["Is anything blocking the launch?"])[0]
    result = index.query(vector=query_vec, top_k=3, include_metadata=True)
    print("Sanity check — top 3 matches for 'Is anything blocking the launch?':")
    for match in result["matches"]:
        meta = match["metadata"]
        print(f"  [{meta['location']}] score={match['score']:.3f} {meta['text'][:100]}...")
