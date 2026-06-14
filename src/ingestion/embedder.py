"""Text embedding using sentence-transformers."""

import logging
from typing import List

logger = logging.getLogger(__name__)


class Embedder:
    """Generates text embeddings using SentenceTransformer models."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize the embedder with a SentenceTransformer model.

        Args:
            model_name: Name of the sentence-transformers model.
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is required. "
                "Install with: pip install sentence-transformers"
            ) from exc

        logger.info("Loading embedding model: %s", model_name)
        self._model = SentenceTransformer(model_name)
        self._model_name = model_name
        self._dimensions = self._model.get_sentence_embedding_dimension()
        logger.info(
            "Model loaded. Dimensions: %d", self._dimensions
        )

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model_name

    @property
    def dimensions(self) -> int:
        """Return the embedding dimensions."""
        return self._dimensions

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed.

        Returns:
            List of floats representing the embedding vector.

        Raises:
            ValueError: If text is empty.
        """
        if not text or not text.strip():
            raise ValueError("Cannot embed empty text")

        embedding = self._model.encode(
            text,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of input texts to embed.

        Returns:
            List of embedding vectors.

        Raises:
            ValueError: If texts list is empty or contains empty strings.
        """
        if not texts:
            raise ValueError("Cannot embed empty batch")

        non_empty = [t for t in texts if t and t.strip()]
        if not non_empty:
            raise ValueError("All texts in batch are empty")

        if len(non_empty) != len(texts):
            skipped = len(texts) - len(non_empty)
            logger.warning(
                "Skipping %d empty texts in batch", skipped
            )

        embeddings = self._model.encode(
            non_empty,
            show_progress_bar=True,
            normalize_embeddings=True,
            batch_size=64,
        )
        return [emb.tolist() for emb in embeddings]
