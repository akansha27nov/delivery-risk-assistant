"""
Embed chunks (OpenAI) and store them in Pinecone.
"""

import os
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from config import (
    OPENAI_API_KEY,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    EMBEDDING_MODEL,
    EMBEDDING_DIM
)
from rerank import rerank 

load_dotenv()

openai_client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
INDEX_NAME = pc.Index(PINECONE_INDEX_NAME)

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


def _cleanup_default_namespace(index):
    """
    Purges the '__default__' namespace, which only has vectors in it if an
    older version of this script ran before namespace support was added.
    Nothing should ever be upserted there going forward -- every write now
    always specifies a project namespace -- so if it's empty this is a
    harmless no-op.
    """
    try:
        index.delete(delete_all=True, namespace="__default__")
    except Exception as e:
        if "404" not in str(e) and "Namespace not found" not in str(e):
            raise


def _upsert_chunks(index, chunks: list[dict], project: str, batch_size: int = 50):
    """Shared embed+upsert loop, used by both a full rebuild and a live single-doc add."""
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        vectors = _embed([c["text"] for c in batch])
        index.upsert(
            vectors=[
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
            ],
            namespace=project,
        )


def build_vector_store(chunks: list[dict], batch_size: int = 50):
    """
    Embed every chunk via OpenAI and upsert into Pinecone, one namespace
    per project (namespace = project id, e.g. "atlas" / "nova"). Namespaces
    give physical separation between projects -- a query scoped to the
    "atlas" namespace cannot return a "nova" chunk, full stop, regardless
    of how semantically similar the text is.

    Deletes and re-upserts each project's namespace on every run so
    re-running after editing knowledge_base/ doesn't leave stale or duplicate
    vectors behind. Use this for the static demo corpus (knowledge_base/); for
    adding one new document to an already-built index without wiping it,
    use add_document_to_project() instead.
    """
    index = _ensure_index()
    _cleanup_default_namespace(index)
    projects = sorted(set(c["project"] for c in chunks))

    for project in projects:
        project_chunks = [c for c in chunks if c["project"] == project]

        try:
            index.delete(delete_all=True, namespace=project)
        except Exception as e:
            # First run: namespace doesn't exist yet because nothing has
            # been upserted to it. Pinecone raises a 404 for this instead
            # of a no-op -- safe to ignore.
            if "404" not in str(e) and "Namespace not found" not in str(e):
                raise

        _upsert_chunks(index, project_chunks, project, batch_size)
    return index


def add_document_to_project(chunks: list[dict], project: str, batch_size: int = 50):
    """
    Live document upload path (Phase 5 UI): embed and upsert a small batch
    of new chunks -- typically from ONE newly uploaded file -- into an
    EXISTING project namespace, WITHOUT deleting what's already there.
    This is the non-destructive counterpart to build_vector_store(), used
    when someone uploads a new document into a project through the app
    instead of rebuilding the whole demo corpus from knowledge_base/.
    """
    index = _ensure_index()
    _upsert_chunks(index, chunks, project, batch_size)
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
    print(f"Pinecone index '{INDEX_NAME}' — vectors per namespace:")
    for namespace, ns_stats in stats["namespaces"].items():
        print(f"  [{namespace}] {ns_stats['vector_count']} chunks")

    # Sanity check, run separately per project to prove isolation
    query = "Is anything blocking the launch?"
    query_vec = _embed([query])[0]
    for project in stats["namespaces"]:
        print(f"\nSanity check — '{query}' (namespace: {project}):")
        result = index.query(vector=query_vec, top_k=3, include_metadata=True, namespace=project)
        for match in result["matches"]:
            meta = match["metadata"]
            print(f"  [{meta['location']}] score={match['score']:.3f} {meta['text'][:100]}...")
