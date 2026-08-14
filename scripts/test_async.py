# src/test_async.py
import asyncio

from dotenv import load_dotenv

# Load env variables before importing modules that use them
load_dotenv()

from retrieval import gather_evidence_async


async def test_retrieval():
    print("Testing async evidence gathering for 'atlas'...")
    chunks = await gather_evidence_async(
        "atlas", "What are this week's top delivery risks?"
    )

    print(f"\nSuccessfully gathered {len(chunks)} unique chunks concurrently!")
    for idx, chunk in enumerate(chunks, 1):
        print(f"\n  {idx}. ID: {chunk['chunk_id']}")
        print(f"     Location: {chunk['location']}")
        print(f"     Score: {chunk.get('score')}")


if __name__ == "__main__":
    asyncio.run(test_retrieval())
