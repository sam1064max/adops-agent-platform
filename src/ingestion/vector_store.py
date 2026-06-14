"""Qdrant vector store interface for document storage and retrieval."""

import logging
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointIdsList,
        PointStruct,
        VectorParams,
    )
except ImportError as exc:
    raise ImportError(
        "qdrant-client is required. "
        "Install with: pip install qdrant-client"
    ) from exc


def _parse_distance(distance: str) -> Distance:
    """Convert distance string to Qdrant Distance enum."""
    mapping = {
        "cosine": Distance.COSINE,
        "euclid": Distance.EUCLID,
        "euclidean": Distance.EUCLID,
        "dot": Distance.DOT,
        "manhattan": Distance.MANHATTAN,
    }
    distance_lower = distance.lower()
    if distance_lower not in mapping:
        raise ValueError(
            f"Unknown distance metric: {distance}. "
            f"Supported: {list(mapping.keys())}"
        )
    return mapping[distance_lower]


class VectorStore:
    """Interface for Qdrant vector database operations."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "adops_knowledge",
    ):
        """Initialize the Qdrant client.

        Args:
            host: Qdrant server host.
            port: Qdrant server port.
            collection_name: Name of the collection to use.
        """
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self._client = QdrantClient(host=host, port=port)
        logger.info(
            "Connected to Qdrant at %s:%d (collection: %s)",
            host,
            port,
            collection_name,
        )

    @property
    def client(self) -> QdrantClient:
        """Return the underlying Qdrant client."""
        return self._client

    def create_collection(
        self,
        dimension: int,
        distance: str = "cosine",
    ) -> None:
        """Create a new collection in Qdrant.

        Args:
            dimension: Vector dimension size.
            distance: Distance metric (cosine, euclid, dot, manhattan).
        """
        distance_enum = _parse_distance(distance)

        existing = [
            c.name for c in self._client.get_collections().collections
        ]
        if self.collection_name in existing:
            logger.info(
                "Collection '%s' already exists, skipping creation",
                self.collection_name,
            )
            return

        self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(
                size=dimension,
                distance=distance_enum,
            ),
        )
        logger.info(
            "Created collection '%s' (dim=%d, dist=%s)",
            self.collection_name,
            dimension,
            distance,
        )

    def upsert_documents(
        self,
        ids: List[str],
        vectors: List[List[float]],
        payloads: List[Dict[str, Any]],
    ) -> None:
        """Insert or update documents in the vector store.

        Args:
            ids: List of document IDs.
            vectors: List of embedding vectors.
            payloads: List of metadata payloads.

        Raises:
            ValueError: If input lists have mismatched lengths.
        """
        if not (len(ids) == len(vectors) == len(payloads)):
            raise ValueError(
                f"Length mismatch: ids={len(ids)}, "
                f"vectors={len(vectors)}, "
                f"payloads={len(payloads)}"
            )

        if not ids:
            logger.warning("No documents to upsert")
            return

        points = []
        for doc_id, vector, payload in zip(ids, vectors, payloads):
            # Ensure ID is a valid UUID or integer
            try:
                point_id = str(uuid.UUID(doc_id))
            except ValueError:
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, doc_id))

            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            )

        # Upsert in batches of 100
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self._client.upsert(
                collection_name=self.collection_name,
                points=batch,
            )

        logger.info(
            "Upserted %d documents into '%s'",
            len(points),
            self.collection_name,
        )

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar documents.

        Args:
            query_vector: Query embedding vector.
            top_k: Number of results to return.
            filter_dict: Optional metadata filter. Example:
                {"source_file": "readme.md"}

        Returns:
            List of search results with 'id', 'score', 'payload'.
        """
        query_filter = None
        if filter_dict:
            conditions = []
            for key, value in filter_dict.items():
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value),
                    )
                )
            query_filter = Filter(must=conditions)

        results = self._client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=query_filter,
        )

        formatted = []
        for result in results:
            formatted.append(
                {
                    "id": result.id,
                    "score": result.score,
                    "payload": result.payload,
                }
            )

        logger.info(
            "Search returned %d results from '%s'",
            len(formatted),
            self.collection_name,
        )
        return formatted

    def delete_collection(self) -> None:
        """Delete the collection from Qdrant."""
        try:
            self._client.delete_collection(
                collection_name=self.collection_name
            )
            logger.info(
                "Deleted collection '%s'", self.collection_name
            )
        except Exception:
            logger.exception(
                "Failed to delete collection '%s'",
                self.collection_name,
            )
            raise

    def collection_info(self) -> Dict[str, Any]:
        """Get information about the collection.

        Returns:
            Dictionary with collection metadata.
        """
        try:
            info = self._client.get_collection(
                collection_name=self.collection_name
            )
            result = {
                "name": self.collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": str(info.status),
                "optimizer_status": str(info.optimizer_status),
                "config": {
                    "params": {
                        "vectors": {
                            "size": info.config.params.vectors.size,
                            "distance": str(
                                info.config.params.vectors.distance
                            ),
                        }
                    }
                },
            }
            return result
        except Exception:
            logger.exception("Failed to get collection info")
            return {"name": self.collection_name, "error": "not found"}
