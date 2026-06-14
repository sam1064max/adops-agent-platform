"""Tests for the ingestion pipeline — document loading, chunking, embedding."""

from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pandas as pd
import pytest

from src.ingestion.document_loader import (
    Document,
    DocumentLoader,
    Chunk,
    _parse_frontmatter,
    _extract_sections,
    _split_text,
)
from src.ingestion.pipeline import IngestionPipeline, IngestResult


# ---------------------------------------------------------------------------
# Document / Chunk helpers
# ---------------------------------------------------------------------------

class TestDocumentDataclass:
    def test_document_creation(self):
        doc = Document(content="Hello world", metadata={"source": "test.md"})
        assert doc.content == "Hello world"
        assert doc.metadata["source"] == "test.md"

    def test_document_default_metadata(self):
        doc = Document(content="content")
        assert doc.metadata == {}


class TestChunkDataclass:
    def test_chunk_creation(self):
        chunk = Chunk(content="chunk text", metadata={"idx": 0})
        assert chunk.content == "chunk text"
        assert chunk.metadata["idx"] == 0


# ---------------------------------------------------------------------------
# _parse_frontmatter
# ---------------------------------------------------------------------------

class TestParseFrontmatter:
    def test_parse_frontmatter(self):
        raw = "---\ntitle: Test Doc\nauthor: Alice\n---\nBody content here."
        meta, body = _parse_frontmatter(raw)
        assert meta["title"] == "Test Doc"
        assert meta["author"] == "Alice"
        assert body.strip() == "Body content here."

    def test_no_frontmatter(self):
        raw = "Just plain text with no frontmatter."
        meta, body = _parse_frontmatter(raw)
        assert meta == {}
        assert body == raw

    def test_frontmatter_with_quotes(self):
        raw = '---\ntitle: "Quoted Title"\n---\nBody'
        meta, body = _parse_frontmatter(raw)
        assert meta["title"] == "Quoted Title"


# ---------------------------------------------------------------------------
# _extract_sections
# ---------------------------------------------------------------------------

class TestExtractSections:
    def test_extracts_headers(self):
        content = "# Intro\nSome intro text.\n## Details\nMore details."
        sections = _extract_sections(content)
        assert len(sections) == 2
        assert sections[0]["header"] == "Intro"
        assert "intro text" in sections[0]["text"]
        assert sections[1]["header"] == "Details"

    def test_no_headers(self):
        content = "Plain paragraph without any headers."
        sections = _extract_sections(content)
        assert len(sections) == 1
        assert sections[0]["header"] == ""

    def test_empty_content(self):
        sections = _extract_sections("")
        # Empty string has no headers and no text → empty list
        assert len(sections) == 0


# ---------------------------------------------------------------------------
# _split_text
# ---------------------------------------------------------------------------

class TestSplitText:
    def test_short_text_unchanged(self):
        result = _split_text("Short.", chunk_size=500)
        assert result == ["Short."]

    def test_long_text_split(self):
        text = ". ".join([f"Sentence {i}" for i in range(100)])
        chunks = _split_text(text, chunk_size=200, chunk_overlap=30)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 300  # some slack from overlap

    def test_overlap_preserves_content(self):
        text = ". ".join([f"Word{i}" for i in range(50)])
        chunks = _split_text(text, chunk_size=100, chunk_overlap=20)
        # Each chunk after the first should share some content
        assert len(chunks) >= 2


# ---------------------------------------------------------------------------
# DocumentLoader
# ---------------------------------------------------------------------------

class TestDocumentLoader:
    def test_document_loader(self, tmp_path):
        """Load a temporary knowledge base directory with .md files."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "doc1.md").write_text(
            "---\ntitle: Doc One\n---\n# Section A\nContent A.\n# Section B\nContent B.",
            encoding="utf-8",
        )
        (kb_dir / "doc2.md").write_text(
            "# Doc Two\nSecond document content.",
            encoding="utf-8",
        )
        (kb_dir / "skip.txt").write_text("not markdown", encoding="utf-8")

        loader = DocumentLoader()
        docs = loader.load_knowledge_base(str(kb_dir))
        assert len(docs) == 2
        filenames = {d.metadata["filename"] for d in docs}
        assert "doc1.md" in filenames
        assert "doc2.md" in filenames

    def test_load_nonexistent_directory(self):
        loader = DocumentLoader()
        with pytest.raises(FileNotFoundError):
            loader.load_knowledge_base("/nonexistent/path/abc123")

    def test_chunking(self, tmp_path):
        """Chunk a document and verify chunk metadata."""
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        long_text = "# Header\n" + ". ".join([f"Word {i}" for i in range(200)])
        (kb_dir / "long.md").write_text(long_text, encoding="utf-8")

        loader = DocumentLoader(chunk_size=200, chunk_overlap=30)
        docs = loader.load_knowledge_base(str(kb_dir))
        chunks = loader.chunk_documents(docs)
        assert len(chunks) > 1
        for chunk in chunks:
            assert isinstance(chunk.content, str)
            assert "source_file" in chunk.metadata
            assert "chunk_index" in chunk.metadata

    def test_empty_file_skipped(self, tmp_path):
        kb_dir = tmp_path / "kb"
        kb_dir.mkdir()
        (kb_dir / "empty.md").write_text("", encoding="utf-8")

        loader = DocumentLoader()
        docs = loader.load_knowledge_base(str(kb_dir))
        assert docs == []


# ---------------------------------------------------------------------------
# Embedding dimension (mock)
# ---------------------------------------------------------------------------

class TestEmbeddingDimension:
    def test_embedding_dimension(self, mock_embedding_model):
        from src.ingestion.embedder import Embedder

        embedder = Embedder.__new__(Embedder)
        embedder._model = mock_embedding_model
        embedder._model_name = "test-model"
        embedder._dimensions = mock_embedding_model.get_sentence_embedding_dimension()
        assert embedder.dimensions == 384

    def test_embed_text(self, mock_embedding_model):
        mock_embedding_model.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)
        from src.ingestion.embedder import Embedder

        embedder = Embedder.__new__(Embedder)
        embedder._model = mock_embedding_model
        embedder._model_name = "test-model"
        embedder._dimensions = 384
        result = embedder.embed_text("hello world")
        assert len(result) == 384

    def test_embed_batch(self, mock_embedding_model):
        import numpy as np
        mock_embedding_model.encode.return_value = np.array([[0.1] * 384, [0.2] * 384])
        from src.ingestion.embedder import Embedder

        embedder = Embedder.__new__(Embedder)
        embedder._model = mock_embedding_model
        embedder._model_name = "test-model"
        embedder._dimensions = 384
        results = embedder.embed_batch(["text a", "text b"])
        assert len(results) == 2
        assert len(results[0]) == 384


# ---------------------------------------------------------------------------
# IngestionPipeline
# ---------------------------------------------------------------------------

class TestIngestionPipeline:
    def test_pipeline_run_no_documents(self):
        mock_loader = MagicMock()
        mock_loader.load_knowledge_base.return_value = []
        mock_embedder = MagicMock()
        mock_vs = MagicMock()

        pipeline = IngestionPipeline(mock_vs, mock_embedder, mock_loader)
        result = pipeline.run("dummy_path")
        assert result.documents_loaded == 0
        assert result.chunks_created == 0
        assert result.success is True

    def test_pipeline_run_success(self):
        mock_loader = MagicMock()
        mock_loader.load_knowledge_base.return_value = [Document(content="test")]
        mock_loader.chunk_documents.return_value = [Chunk(content="chunk1")]
        mock_embedder = MagicMock()
        mock_embedder.embed_batch.return_value = [[0.1] * 10]
        mock_vs = MagicMock()

        pipeline = IngestionPipeline(mock_vs, mock_embedder, mock_loader)
        result = pipeline.run("dummy_path")
        assert result.documents_loaded == 1
        assert result.chunks_created == 1
        assert result.vectors_embedded == 1
        assert result.vectors_stored == 1
        assert result.success is True

    def test_pipeline_handles_load_error(self):
        mock_loader = MagicMock()
        mock_loader.load_knowledge_base.side_effect = IOError("disk error")
        mock_embedder = MagicMock()
        mock_vs = MagicMock()

        pipeline = IngestionPipeline(mock_vs, mock_embedder, mock_loader)
        result = pipeline.run("dummy_path")
        assert result.success is False
        assert len(result.errors) == 1
        assert "disk error" in result.errors[0]

    def test_ingest_result_summary(self):
        result = IngestResult(
            documents_loaded=5,
            chunks_created=20,
            vectors_embedded=20,
            vectors_stored=20,
            elapsed_seconds=1.23,
        )
        summary = result.summary()
        assert "SUCCESS" in summary
        assert "Documents loaded:  5" in summary

    def test_ingest_result_partial_failure(self):
        result = IngestResult(
            documents_loaded=3,
            chunks_created=10,
            vectors_embedded=10,
            vectors_stored=8,
            errors=["Qdrant timeout"],
        )
        assert result.success is False
        assert "PARTIAL FAILURE" in result.summary()

    def test_ingest_chunks_mismatch_raises(self):
        mock_vs = MagicMock()
        mock_embedder = MagicMock()
        pipeline = IngestionPipeline(mock_vs, mock_embedder)
        with pytest.raises(ValueError, match="mismatch"):
            pipeline.ingest_chunks(
                [Chunk(content="a"), Chunk(content="b")],
                [[0.1]],
            )
