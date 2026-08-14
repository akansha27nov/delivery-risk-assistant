import asyncio

from retrieval import gather_evidence_async


async def main():
    chunks = await gather_evidence_async("atlas", "What are the delivery risks?")
    print(f"Retrieved and reranked {len(chunks)} chunks.")
    for c in chunks[:3]:
        print(
            f"- [{c['chunk_id']}] (Score: {c.get('rerank_score', 'N/A')}): {c['text'][:60]}..."
        )


if __name__ == "__main__":
    asyncio.run(main())
