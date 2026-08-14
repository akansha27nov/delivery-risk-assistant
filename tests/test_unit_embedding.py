# tests/test_unit_embedding.py
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import embedding


@patch("embedding.OpenAI")
def test_embed_helper(mock_openai_cls):
    """Test private _embed helper formats OpenAI responses correctly."""
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1, 0.2, 0.3])]
    )

    with patch.object(embedding, "openai_client", mock_client):
        result = embedding._embed(["test text"])
        assert result == [[0.1, 0.2, 0.3]]


@patch("embedding.Pinecone")
def test_ensure_index_creates_when_missing(mock_pc_cls):
    """Test _ensure_index creates a new index if it does not already exist."""
    mock_pc = MagicMock()
    mock_pc_cls.return_value = mock_pc
    mock_pc.list_indexes.return_value = [{"name": "other-index"}]

    with (
        patch.object(embedding, "pc", mock_pc),
        patch.object(embedding, "INDEX_NAME", "test-index"),
    ):
        embedding._ensure_index()
        mock_pc.create_index.assert_called_once()
        mock_pc.Index.assert_called_with("test-index")


@patch("embedding.Pinecone")
def test_ensure_index_already_exists(mock_pc_cls):
    """Test _ensure_index skips creation if the index already exists."""
    mock_pc = MagicMock()
    mock_pc_cls.return_value = mock_pc
    mock_pc.list_indexes.return_value = [{"name": "test-index"}]

    with (
        patch.object(embedding, "pc", mock_pc),
        patch.object(embedding, "INDEX_NAME", "test-index"),
    ):
        embedding._ensure_index()
        mock_pc.create_index.assert_not_called()
        mock_pc.Index.assert_called_with("test-index")


def test_cleanup_default_namespace():
    """Test _cleanup_default_namespace suppresses 404 and Namespace not found errors, but raises others."""
    mock_index = MagicMock()

    # 404 error suppressed
    mock_index.delete.side_effect = Exception("404 Not Found")
    embedding._cleanup_default_namespace(mock_index)

    # Namespace not found suppressed
    mock_index.delete.side_effect = Exception("Namespace not found")
    embedding._cleanup_default_namespace(mock_index)

    # Other exception raised
    mock_index.delete.side_effect = Exception("500 Server Error")
    with pytest.raises(Exception, match="500 Server Error"):
        embedding._cleanup_default_namespace(mock_index)


@patch("embedding.OpenAI")
@patch("embedding.Pinecone")
def test_build_vector_store(mock_pc_cls, mock_openai_cls):
    """Test build_vector_store iterates over projects, handles namespace deletion exceptions, and upserts chunks."""
    mock_pc = MagicMock()
    mock_pc_cls.return_value = mock_pc
    mock_index = MagicMock()
    mock_pc.Index.return_value = mock_index
    mock_pc.list_indexes.return_value = [{"name": "test-index"}]

    mock_openai = MagicMock()
    mock_openai_cls.return_value = mock_openai
    mock_openai.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1] * 1536)]
    )

    # Raise non-404 error on delete to verify it gets raised
    mock_index.delete.side_effect = Exception("Fatal delete error")

    with (
        patch.object(embedding, "pc", mock_pc),
        patch.object(embedding, "openai_client", mock_openai),
        patch.object(embedding, "INDEX_NAME", "test-index"),
    ):
        chunks = [
            {
                "chunk_id": "c1",
                "source": "a.md",
                "location": "loc",
                "text": "sample",
                "project": "atlas",
            }
        ]

        with pytest.raises(Exception, match="Fatal delete error"):
            embedding.build_vector_store(chunks)

        # Now test with 404 error (should pass successfully)
        mock_index.delete.side_effect = Exception("404 Not Found")
        idx = embedding.build_vector_store(chunks)
        assert idx == mock_index


@patch("embedding.Pinecone")
def test_add_document_to_project(mock_pc_cls):
    """Test adding single documents to an existing project namespace."""
    mock_pc = MagicMock()
    mock_pc_cls.return_value = mock_pc
    mock_index = MagicMock()
    mock_pc.Index.return_value = mock_index
    mock_pc.list_indexes.return_value = [{"name": "test-index"}]

    with (
        patch.object(embedding, "pc", mock_pc),
        patch.object(embedding, "INDEX_NAME", "test-index"),
        patch("embedding._embed", return_value=[[0.1] * 1536]),
    ):
        chunks = [
            {
                "chunk_id": "c2",
                "source": "b.md",
                "location": "loc",
                "text": "new data",
                "project": "atlas",
            }
        ]
        idx = embedding.add_document_to_project(chunks, "atlas")
        assert idx == mock_index


@patch("embedding.Pinecone")
def test_get_index(mock_pc_cls):
    """Test get_index successfully connects to the existing Pinecone index reference."""
    mock_pc = MagicMock()
    mock_pc_cls.return_value = mock_pc

    with (
        patch.object(embedding, "pc", mock_pc),
        patch.object(embedding, "INDEX_NAME", "test-index"),
    ):
        embedding.get_index()
        mock_pc.Index.assert_called_with("test-index")


@patch("embedding.OpenAI")
@patch("embedding.Pinecone")
def test_build_vector_store_unexpected_deletion_exception(mock_pc_cls, mock_openai_cls):
    """Test build_vector_store re-raises unexpected exceptions (non-404) during project namespace deletion."""
    mock_pc = MagicMock()
    mock_pc_cls.return_value = mock_pc
    mock_index = MagicMock()
    mock_pc.Index.return_value = mock_index
    mock_pc.list_indexes.return_value = [{"name": "test-index"}]

    mock_openai = MagicMock()
    mock_openai_cls.return_value = mock_openai

    # Allow default namespace cleanup to pass, then raise unexpected error on project delete
    def delete_side_effect(*args, **kwargs):
        if kwargs.get("namespace") == "__default__":
            return
        raise Exception("Unexpected Service Failure")

    mock_index.delete.side_effect = delete_side_effect

    with (
        patch.object(embedding, "pc", mock_pc),
        patch.object(embedding, "openai_client", mock_openai),
        patch.object(embedding, "INDEX_NAME", "test-index"),
    ):
        chunks = [
            {
                "chunk_id": "c1",
                "source": "a.md",
                "location": "loc",
                "text": "sample",
                "project": "atlas",
            }
        ]

        with pytest.raises(Exception, match="Unexpected Service Failure"):
            embedding.build_vector_store(chunks)
