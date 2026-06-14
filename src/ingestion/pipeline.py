"""RAG ingestion pipeline orchestrating loading, embedding, and storage."""

import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .document_loader import Chunk, Document, DocumentLoader
from .embedder import Embedder
from .vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class IngestResult:
    """Result of a pipeline ingestion run."""

    documents_loaded: int = 0
    chunks_created: int = 0
    vectors_embedded: int = 0
    vectors_stored: int = 0
    elapsed_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Return True if no errors occurred."""
        return len(self.errors) == 0

    def summary(self) -> str:
        """Return a human-readable summary."""
        status = "SUCCESS" if self.success else "PARTIAL FAILURE"
        lines = [
            f"=== Ingestion {status} ===",
            f"Documents loaded:  {self.documents_loaded}",
            f"Chunks created:    {self.chunks_created}",
            f"Vectors embedded:  {self.vectors_embedded}",
            f"Vectors stored:    {self.vectors_stored}",
            f"Elapsed:           {self.elapsed_seconds:.2f}s",
        ]
        if self.errors:
            lines.append(f"Errors: {len(self.errors)}")
            for err in self.errors:
                lines.append(f"  - {err}")
        return "\n".join(lines)


class IngestionPipeline:
    """Orchestrates the full RAG ingestion pipeline."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedder: Embedder,
        document_loader: Optional[DocumentLoader] = None,
    ):
        """Initialize the pipeline with its components.

        Args:
            vector_store: Qdrant vector store instance.
            embedder: Sentence-transformers embedder instance.
            document_loader: Document loader instance. Creates default if None.
        """
        self.vector_store = vector_store
        self.embedder = embedder
        self.document_loader = document_loader or DocumentLoader()

    def run(
        self, kb_path: str = "knowledge_base/"
    ) -> IngestResult:
        """Execute the full ingestion pipeline.

        Steps:
            1. Load documents from knowledge base
            2. Chunk documents
            3. Embed chunks
            4. Store in Qdrant

        Args:
            kb_path: Path to the knowledge base directory.

        Returns:
            IngestResult with pipeline statistics.
        """
        result = IngestResult()
        start_time = time.time()

        try:
            # Step 1: Load documents
            logger.info("Step 1/4: Loading documents from %s", kb_path)
            documents = self.document_loader.load_knowledge_base(kb_path)
            result.documents_loaded = len(documents)

        except Exception as exc:
            msg = f"Failed to load documents: {exc}"
            logger.error(msg)
            result.errors.append(msg)
            result.elapsed_seconds = time.time() - start_time
            return result

        if not documents:
            logger.warning("No documents found. Pipeline complete.")
            result.elapsed_seconds = time.time() - start_time
            return result

        try:
            # Step 2: Chunk documents
            logger.info("Step 2/4: Chunking documents")
            chunks = self.document_loader.chunk_documents(documents)
            result.chunks_created = len(chunks)

        except Exception as exc:
            msg = f"Failed to chunk documents: {exc}"
            logger.error(msg)
            result.errors.append(msg)
            result.elapsed_seconds = time.time() - start_time
            return result

        if not chunks:
            logger.warning("No chunks produced. Pipeline complete.")
            result.elapsed_seconds = time.time() - start_time
            return result

        try:
            # Step 3: Embed chunks
            logger.info(
                "Step 3/4: Embedding %d chunks", len(chunks)
            )
            texts = [c.content for c in chunks]
            embeddings = self.embedder.embed_batch(texts)
            result.vectors_embedded = len(embeddings)

        except Exception as exc:
            msg = f"Failed to embed chunks: {exc}"
            logger.error(msg)
            result.errors.append(msg)
            result.elapsed_seconds = time.time() - start_time
            return result

        try:
            # Step 4: Store in Qdrant
            logger.info(
                "Step 4/4: Storing %d vectors in Qdrant",
                len(embeddings),
            )
            self.ingest_chunks(chunks, embeddings)
            result.vectors_stored = len(embeddings)

        except Exception as exc:
            msg = f"Failed to store vectors: {exc}"
            logger.error(msg)
            result.errors.append(msg)

        result.elapsed_seconds = time.time() - start_time
        logger.info(result.summary())
        return result

    def ingest_documents(self, documents: List[Document]) -> int:
        """Ingest a list of documents into the vector store.

        Args:
            documents: List of Document objects.

        Returns:
            Number of vectors stored.
        """
        chunks = self.document_loader.chunk_documents(documents)
        if not chunks:
            return 0

        texts = [c.content for c in chunks]
        embeddings = self.embedder.embed_batch(texts)
        self.ingest_chunks(chunks, embeddings)
        return len(embeddings)

    def ingest_chunks(
        self,
        chunks: List[Chunk],
        embeddings: List[List[float]],
    ) -> None:
        """Store chunks and their embeddings in Qdrant.

        Args:
            chunks: List of Chunk objects.
            embeddings: Corresponding embedding vectors.

        Raises:
            ValueError: If chunks and embeddings have different lengths.
        """
        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Chunk/embedding count mismatch: "
                f"{len(chunks)} chunks vs {len(embeddings)} embeddings"
            )

        ids: List[str] = []
        vectors: List[List[float]] = []
        payloads: List[Dict[str, Any]] = []

        for chunk, embedding in zip(chunks, embeddings):
            doc_id = str(uuid.uuid4())
            payload = {
                "content": chunk.content,
                **chunk.metadata,
            }
            ids.append(doc_id)
            vectors.append(embedding)
            payloads.append(payload)

        self.vector_store.upsert_documents(ids, vectors, payloads)
        logger.info(
            "Ingested %d chunks into collection '%s'",
            len(chunks),
            self.vector_store.collection_name,
        )
