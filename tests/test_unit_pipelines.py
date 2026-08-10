# tests/test_unit_pipelines.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chunking import _chunk_text_doc, chunk_documents

def test_chunk_text_doc_fallback_large_text():
    """Test chunking multiple paragraphs when no markdown headings exist."""
    large_text = "\n\n".join([f"Paragraph {i}: " + ("Some paragraph text content. " * 20) for i in range(10)])
    chunks = _chunk_text_doc("large_doc.txt", large_text, "atlas", max_chars=500)
    assert len(chunks) > 1
    assert chunks[0]["location"] == "large_doc.txt"

def test_chunk_documents_empty_list():
    """Test chunking handles empty document lists gracefully."""
    chunks = chunk_documents([])
    assert chunks == []

def test_chunk_documents_valid_doc():
    """Test chunking converts document dictionaries into chunks."""
    docs = [
        {
            "type": "text",
            "source": "sample.md",
            "content": "# Section 1\nSome test details.",
            "project": "atlas"
        }
    ]
    chunks = chunk_documents(docs)
    assert len(chunks) == 1
    assert "sample.md" in chunks[0]["chunk_id"]