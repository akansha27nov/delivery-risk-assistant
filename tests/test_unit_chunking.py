# tests/test_unit_chunking.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import chunking


def test_chunk_documents_text_with_headings():
    """Test text chunking handles markdown headings and location strings correctly."""
    doc = {
        "source": "roadmap.md",
        "type": "text",
        "content": "# Phase 1\nInitial planning details.\n\n## Phase 2\nExecution details follow here.",
        "project": "atlas",
    }
    chunks = chunking.chunk_documents([doc])

    assert len(chunks) == 2
    assert chunks[0]["location"] == "roadmap.md — Phase 1"
    assert chunks[1]["location"] == "roadmap.md — Phase 2"
    assert chunks[0]["project"] == "atlas"


def test_chunk_documents_text_inline_heading():
    """Test text chunking when a heading is immediately followed by content without a blank line."""
    doc = {
        "source": "notes.md",
        "type": "text",
        "content": "# ImmediateHeading\nThis text follows right after.",
        "project": "nova",
    }
    chunks = chunking.chunk_documents([doc])

    assert len(chunks) == 1
    assert chunks[0]["location"] == "notes.md — ImmediateHeading"
    assert "This text follows right after." in chunks[0]["text"]


def test_chunk_documents_csv():
    """Test CSV row chunking with ticket IDs and fallback row identifiers."""
    doc = {
        "source": "tickets.csv",
        "type": "csv",
        "rows": [
            {"ticket_id": "ATL-10", "status": "Open", "summary": "Fix bug"},
            {"status": "Closed", "summary": "No ticket id provided"},
        ],
        "project": "atlas",
    }
    chunks = chunking.chunk_documents([doc])

    assert len(chunks) == 2
    assert chunks[0]["chunk_id"] == "tickets.csv::ATL-10"
    assert chunks[1]["chunk_id"] == "tickets.csv::row1"
    assert chunks[1]["location"] == "tickets.csv — row row1"


def test_chunk_documents_empty_and_ignored():
    """Test empty content filtering and handling of unrecognized document types."""
    docs = [
        {
            "source": "empty.md",
            "type": "text",
            "content": "\n\n   \n",
            "project": "atlas",
        },
        {
            "source": "unknown.xyz",
            "type": "unknown",
            "content": "data",
            "project": "atlas",
        },
    ]
    chunks = chunking.chunk_documents(docs)
    assert len(chunks) == 0


def test_chunk_documents_isolated_heading():
    """Test text chunking handles markdown headings that stand completely alone without trailing text."""
    doc = {
        "source": "isolated.md",
        "type": "text",
        "content": "# Standalone Heading\n\n## Another Heading\nSome content here.",
        "project": "atlas",
    }
    chunks = chunking.chunk_documents([doc])
    assert len(chunks) == 1
    assert chunks[0]["location"] == "isolated.md — Another Heading"
    assert "Some content here." in chunks[0]["text"]
