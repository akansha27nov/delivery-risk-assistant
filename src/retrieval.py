"""
Retrieve the most relevant chunks for a project, using
multi-angle retrieval instead of a single similarity search.

A single generic query ("what are this week's top delivery risks?") only
surfaces whatever happens to be textually similar to that exact wording.
Testing showed this misses whole risk categories: querying about
"blockers" never surfaced the scope-creep email or the exec status
contradiction, because neither chunk is textually about "blocking" --
they're about different things that are ALSO risks.

Fix: run one retrieval pass per risk "angle", pool the results
(deduplicated by chunk_id), then rerank the pool against the user's
actual question so final ordering still reflects real relevance, not
just angle membership.

"""
import asyncio
import os
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone
from config import (
    OPENAI_API_KEY,
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    EMBEDDING_MODEL,
    RISK_ANGLES,
    DEFAULT_TOP_K,
    FINAL_TOP_N     
)
from rerank import rerank 
from logger import get_logger

load_dotenv()

client = OpenAI(api_key=OPENAI_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
logger = get_logger(__name__)

_index = None


def _get_index():
    """
    Lazily create the Pinecone Index client on first use, not at import
    time. Creating it eagerly at module load meant simply IMPORTING this
    module (e.g. transitively via graph.py) made a real network call to
    Pinecone before any function was ever invoked -- a startup-latency and
    reliability risk (a slow/unreachable Pinecone stalls app startup, not
    just a specific retrieval), and it made this module impossible to
    import in any offline/test context.
    """
    global _index
    if _index is None:
        _index = pc.Index(PINECONE_INDEX_NAME)
    return _index

async def query_single_angle(angle: str, query: str, namespace: str, top_k: int = DEFAULT_TOP_K):
    """Query Pinecone asynchronously for a single risk angle."""
    # Note: Pinecone's standard SDK is synchronous, so we run it in an executor 
    # or use its async client if available. Here we wrap the query block.
    loop = asyncio.get_running_loop()
    
    def _pinecone_call():
        logger.debug("Retrieving angle '%s' for namespace '%s'.", angle, namespace)
        response = client.embeddings.create(
            input=f"{query} regarding {angle}",
            model=EMBEDDING_MODEL
        )
        vector = response.data[0].embedding
        return _get_index().query(
            vector=vector,
            top_k=top_k,
            namespace=namespace,
            include_metadata=True
        )

    res = await loop.run_in_executor(None, _pinecone_call)
    chunks = []
    for match in res.get("matches", []):
        meta = match.get("metadata", {})
        chunks.append({
            "chunk_id": match.get("id"),
            "text": meta.get("text"),
            "location": meta.get("location"),
            "score": match.get("score")
        })
    logger.debug("Angle '%s' returned %d chunk(s).", angle, len(chunks))
    return chunks

async def gather_evidence_async(project: str, query: str) -> list:
    """Gathers evidence across all risk angles concurrently using asyncio."""
    namespace = project.lower()
    logger.info("Gathering evidence for project '%s' across %d angle(s).", namespace, len(RISK_ANGLES))
    
    tasks = [query_single_angle(angle, query, namespace) for angle in RISK_ANGLES]
    results = await asyncio.gather(*tasks)
    
    seen = set()
    unique_chunks = []
    for angle_chunks in results:
        for chunk in angle_chunks:
            if chunk["chunk_id"] not in seen:
                seen.add(chunk["chunk_id"])
                unique_chunks.append(chunk)
                
    # FIX: Use the imported FINAL_TOP_N (8) for the validated pipeline threshold
    reranked_chunks = rerank(query, unique_chunks, top_n=FINAL_TOP_N)
    logger.info("Gathered %d unique chunk(s); reranked to %d chunk(s).", len(unique_chunks), len(reranked_chunks))
                
    return reranked_chunks
