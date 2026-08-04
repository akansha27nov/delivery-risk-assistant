"""
Splits loaded documents (from ingestion.py) into small chunks with metadata,
so each chunk can be cited back to an exact location:

  {"source": filename, "chunk_id": str, "text": str, "location": str}

Two strategies:
  - CSV rows are already the right granularity -> one chunk per row.
  - Text/Markdown is split by paragraph, grouped up to max_chars, tracking
    the current "##" heading so the location string names the section.
"""

MAX_CHARS = 600

def _chunk_text_doc(source: str, content: str, max_chars: int = MAX_CHARS) -> list[dict]:
    chunks = []
    current_heading = None
    buffer, buffer_len, idx = [], 0, 0

    def flush():
        nonlocal buffer, buffer_len, idx
        if not buffer:
            return
        text = "\n\n".join(buffer).strip()
        if text:
            location = source if not current_heading else f"{source} — {current_heading}"
            chunks.append({
                "source": source,
                "chunk_id": f"{source}::chunk{idx}",
                "text": text,
                "location": location,
            })
            idx += 1
        buffer, buffer_len = [], 0

    for para in content.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        first_line = para.splitlines()[0]
        if first_line.startswith("#"):
            flush()
            current_heading = first_line.lstrip("#").strip()
            continue  # heading itself isn't a chunk
        if buffer_len + len(para) > max_chars and buffer:
            flush()
        buffer.append(para)
        buffer_len += len(para)
    flush()
    return chunks


def _chunk_csv_doc(source: str, rows: list[dict]) -> list[dict]:
    chunks = []
    for i, row in enumerate(rows):
        text = "; ".join(f"{k}: {v}" for k, v in row.items() if v)
        ticket_id = row.get("ticket_id") or f"row{i}"
        chunks.append({
            "source": source,
            "chunk_id": f"{source}::{ticket_id}",
            "text": text,
            "location": f"{source} — row {ticket_id}",
        })
    return chunks


def chunk_documents(documents: list[dict], max_chars: int = MAX_CHARS) -> list[dict]:
    all_chunks = []
    for doc in documents:
        if doc["type"] == "text":
            all_chunks.extend(_chunk_text_doc(doc["source"], doc["content"], max_chars))
        elif doc["type"] == "csv":
            all_chunks.extend(_chunk_csv_doc(doc["source"], doc["rows"]))
    return all_chunks


if __name__ == "__main__":
    from ingestion import load_documents

    docs = load_documents()
    chunks = chunk_documents(docs)

    print(f"{len(docs)} documents -> {len(chunks)} chunks\n")

    from collections import Counter
    counts = Counter(c["source"] for c in chunks)
    for source, n in counts.items():
        print(f"  {source:<30} {n} chunks")

    print("\n--- Sample chunk (markdown, section-aware) ---")
    sample = next(c for c in chunks if c["source"] == "nova_incident_postmortem.md")
    print(f"chunk_id: {sample['chunk_id']}")
    print(f"location: {sample['location']}")
    print(f"text: {sample['text'][:200]}...")

    print("\n--- Sample chunk (CSV row) ---")
    sample = next(c for c in chunks if c["source"] == "ticket_export.csv" and "ATL-142" in c["chunk_id"])
    print(f"chunk_id: {sample['chunk_id']}")
    print(f"location: {sample['location']}")
    print(f"text: {sample['text']}")
