"""
Phase 2, Step 2: Chunking.

Splits loaded documents (from ingestion.py) into small chunks with metadata,
carrying the "project" tag through so it can flow into Pinecone as a
namespace later:

  {"source", "chunk_id", "text", "location", "project"}

Two strategies:
  - CSV rows are already the right granularity -> one chunk per row.
  - Text/Markdown is split by paragraph, grouped up to max_chars, tracking
    the current "##" heading so the location string names the section.
"""

from logger import get_logger

MAX_CHARS = 600
logger = get_logger(__name__)


def _chunk_text_doc(
    source: str, content: str, project: str, max_chars: int = MAX_CHARS
) -> list[dict]:
    chunks = []
    current_heading = None
    buffer, buffer_len, idx = [], 0, 0

    def flush():
        nonlocal buffer, buffer_len, idx
        if not buffer:
            return
        text = "\n\n".join(buffer).strip()
        if text:
            location = (
                source if not current_heading else f"{source} — {current_heading}"
            )
            chunks.append(
                {
                    "source": source,
                    "chunk_id": f"{source}::chunk{idx}",
                    "text": text,
                    "location": location,
                    "project": project,
                }
            )
            idx += 1
        buffer, buffer_len = [], 0

    for para in content.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        lines = para.splitlines()
        if lines[0].startswith("#"):
            flush()
            current_heading = lines[0].lstrip("#").strip()
            remainder = "\n".join(lines[1:]).strip()
            if not remainder:
                continue  # heading was on its own -- nothing else in this paragraph
            para = (
                remainder  # heading was immediately followed by content, no blank line
            )
        if buffer_len + len(para) > max_chars and buffer:
            flush()
        buffer.append(para)
        buffer_len += len(para)
    flush()
    return chunks


def _chunk_csv_doc(source: str, rows: list[dict], project: str) -> list[dict]:
    chunks = []
    for i, row in enumerate(rows):
        text = "; ".join(f"{k}: {v}" for k, v in row.items() if v)
        ticket_id = row.get("ticket_id") or f"row{i}"
        chunks.append(
            {
                "source": source,
                "chunk_id": f"{source}::{ticket_id}",
                "text": text,
                "location": f"{source} — row {ticket_id}",
                "project": project,
            }
        )
    return chunks


def chunk_documents(documents: list[dict], max_chars: int = MAX_CHARS) -> list[dict]:
    all_chunks = []
    for doc in documents:
        if doc["type"] == "text":
            all_chunks.extend(
                _chunk_text_doc(
                    doc["source"], doc["content"], doc["project"], max_chars
                )
            )
        elif doc["type"] == "csv":
            all_chunks.extend(
                _chunk_csv_doc(doc["source"], doc["rows"], doc["project"])
            )
    return all_chunks


if __name__ == "__main__":  # pragma: no cover
    from ingestion import load_documents

    docs = load_documents()
    chunks = chunk_documents(docs)

    logger.info("%d document(s) -> %d chunk(s).", len(docs), len(chunks))

    from collections import Counter

    by_project = Counter(c["project"] for c in chunks)
    for project, n in by_project.items():
        logger.info("[%s] %d chunk(s)", project, n)

    logger.info("Sample chunk, confirming project tag flowed through")
    sample = next(
        c
        for c in chunks
        if c["source"] == "ticket_export.csv" and "ATL-142" in c["chunk_id"]
    )
    logger.info("chunk_id: %s", sample["chunk_id"])
    logger.info("project: %s", sample["project"])
    logger.info("location: %s", sample["location"])
