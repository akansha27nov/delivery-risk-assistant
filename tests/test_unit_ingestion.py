# tests/test_unit_ingestion.py
import sys
import json
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import ingestion

def test_load_documents_mocked_files(tmp_path):
    """Verify load_documents processes both text and CSV files correctly with an isolated test directory and manifest."""
    kb_dir = tmp_path / "knowledge_base"
    kb_dir.mkdir()
    
    # Create a markdown file and a CSV file inside the temp knowledge base
    md_file = kb_dir / "notes.md"
    md_file.write_text("# Test Heading\nTest content")
    
    csv_file = kb_dir / "data.csv"
    csv_file.write_text("col1,col2\nval1,val2")
    
    # Create a matching temporary manifest file
    manifest_file = tmp_path / "project_manifest.json"
    mock_manifest = {"atlas": {"files": ["notes.md", "data.csv"]}}
    manifest_file.write_text(json.dumps(mock_manifest))
    
    docs = ingestion.load_documents(data_dir=kb_dir, manifest_path=manifest_file)
    assert isinstance(docs, list)
    assert len(docs) == 2


def test_load_documents_unlisted_file_raises_error(tmp_path):
    """Verify load_documents raises a ValueError if a file in knowledge_base is missing from the manifest."""
    kb_dir = tmp_path / "knowledge_base"
    kb_dir.mkdir()
    
    test_file = kb_dir / "unlisted.md"
    test_file.write_text("Some content")
    
    manifest_file = tmp_path / "project_manifest.json"
    manifest_file.write_text(json.dumps({"atlas": {"files": ["other.md"]}}))
    
    with pytest.raises(ValueError, match="is in knowledge_base/ but not listed in project_manifest.json"):
        ingestion.load_documents(data_dir=kb_dir, manifest_path=manifest_file)


def test_build_document_from_upload_text():
    """Verify document building from text file uploads handles metadata and string content correctly."""
    filename = "report.md"
    raw_content = "# Uploaded Report\nContent here."
    
    doc = ingestion.build_document_from_upload(filename, raw_content=raw_content, project="atlas")
    assert doc["source"] == "report.md"
    assert doc["project"] == "atlas"
    assert doc["type"] == "text"
    assert "Uploaded Report" in doc["content"]


def test_build_document_from_upload_csv():
    """Verify document building from CSV file uploads parses rows correctly."""
    filename = "metrics.csv"
    raw_content = "metric,value\nvelocity,10\nrisk,low"
    
    doc = ingestion.build_document_from_upload(filename, raw_content=raw_content, project="atlas")
    assert doc["source"] == "metrics.csv"
    assert doc["project"] == "atlas"
    assert doc["type"] == "csv"
    assert len(doc["rows"]) == 2
    assert doc["rows"][0]["metric"] == "velocity"


def test_build_document_from_upload_unsupported():
    """Verify building document from unsupported file type raises ValueError."""
    with pytest.raises(ValueError, match="Unsupported file type"):
        ingestion.build_document_from_upload("archive.zip", raw_content="data", project="atlas")