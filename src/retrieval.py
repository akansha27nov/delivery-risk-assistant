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

from embedding import _embed, get_index
from rerank import rerank

RISK_ANGLES = [
    "blockers, dependencies, or blocked tickets that could delay delivery",
    "scope changes or new work added outside of original sprint planning",
    "team capacity, workload, morale, or attrition signals",
    "status updates and whether they match the evidence in tickets and discussions",
]


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


def gather_evidence(query: str, project: str, k_per_angle: int = 5, final_top_n: int = 8) -> list[dict]:
    """
    Multi-angle retrieval + pooling + final rerank against the original
    query. Deduplicates by chunk_id, keeping the highest retrieval score
    seen for any chunk that surfaced under more than one angle.
    """
    pooled: dict[str, dict] = {}
    for angle in RISK_ANGLES:
        for chunk in retrieve(angle, project=project, k=k_per_angle):
            existing = pooled.get(chunk["chunk_id"])
            if existing is None or chunk["score"] > existing["score"]:
                pooled[chunk["chunk_id"]] = chunk

    candidates = list(pooled.values())
    return rerank(query, candidates, top_n=final_top_n)