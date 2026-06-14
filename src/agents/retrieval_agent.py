"""Retrieval agent - vector search + DB enrichment for the AdOps pipeline."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session

from src.api.metrics import qdrant_latency, retrieval_latency

logger = logging.getLogger(__name__)


class RetrievalAgent:
    """Retrieves relevant context from Qdrant and PostgreSQL.

    Given a classified query (from QueryAgent), this agent:
    1. Embeds the query text.
    2. Performs a vector search in Qdrant.
    3. Enriches results with relational data from Postgres.
    """

    def __init__(
        self,
        qdrant_client: QdrantClient,
        embedding_model: SentenceTransformer,
        db_session_factory: Callable[..., Session],
        collection: str = "adops_knowledge",
        top_k: int = 10,
    ) -> None:
        self._qdrant = qdrant_client
        self._embedder = embedding_model
        self._db_factory = db_session_factory
        self._collection = collection
        self._top_k = top_k

    @retrieval_latency.time()
    def retrieve(
        self,
        text: str,
        entities: Optional[List[Dict[str, Any]]] = None,
        time_range: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Run vector search and return enriched context.

        Args:
            text: The original user query.
            entities: Extracted entities from QueryAgent.
            time_range: Optional time window filter.

        Returns:
            Dict with keys: snippets, campaign_context, inventory_context.
        """
        t0 = time.perf_counter()

        # ── Step 1: embed query ──────────────────────────────────────────
        embedding = self._embedder.encode(text).tolist()

        # ── Step 2: vector search in Qdrant ──────────────────────────────
        qdrant_filter = self._build_filter(entities)
        with qdrant_latency.time():
            results = self._qdrant.search(
                collection_name=self._collection,
                query_vector=embedding,
                limit=self._top_k,
                query_filter=qdrant_filter,
            )

        snippets = []
        for hit in results:
            payload = hit.payload or {}
            snippets.append({
                "id": str(hit.id),
                "score": round(hit.score, 4),
                "content": payload.get("content", ""),
                "source_file": payload.get("source_file", ""),
                "section_header": payload.get("section_header", ""),
            })

        # ── Step 3: DB enrichment ────────────────────────────────────────
        campaign_ids = self._extract_id_values(entities, "campaign_id")
        inventory_ids = self._extract_id_values(entities, "inventory_id")

        campaign_context = self._fetch_campaigns(campaign_ids)
        inventory_context = self._fetch_inventory(inventory_ids)

        elapsed = time.perf_counter() - t0
        logger.info(
            "Retrieved %d snippets, %d campaigns, %d inventory items in %.3fs",
            len(snippets),
            len(campaign_context),
            len(inventory_context),
            elapsed,
        )

        return {
            "snippets": snippets,
            "campaign_context": campaign_context,
            "inventory_context": inventory_context,
        }

    # ── Private helpers ──────────────────────────────────────────────────

    def _build_filter(self, entities: Optional[List[Dict[str, Any]]]) -> Optional[Filter]:
        """Build a Qdrant Filter from extracted entity dicts, if any."""
        if not entities:
            return None

        source_files = []
        for ent in entities:
            if ent.get("type") == "source_file":
                source_files.append(ent["value"])

        if not source_files:
            return None

        conditions = [
            FieldCondition(key="source_file", match=MatchValue(value=sf))
            for sf in source_files
        ]
        return Filter(must=conditions)

    @staticmethod
    def _extract_id_values(
        entities: Optional[List[Dict[str, Any]]], entity_type: str
    ) -> List[str]:
        if not entities:
            return []
        return [e["value"] for e in entities if e.get("type") == entity_type]

    def _fetch_campaigns(self, campaign_ids: List[str]) -> List[Dict[str, Any]]:
        if not campaign_ids:
            return []
        from src.models.database import Campaign

        db = self._db_factory()
        try:
            rows = db.query(Campaign).filter(Campaign.id.in_(campaign_ids)).all()
            return [
                {
                    "campaign_id": c.id,
                    "name": c.name,
                    "advertiser": c.advertiser,
                    "status": c.status,
                    "budget": c.budget,
                    "spend": c.spend,
                    "impressions": c.impressions,
                    "clicks": c.clicks,
                }
                for c in rows
            ]
        except Exception:
            logger.warning("Failed to fetch campaigns", exc_info=True)
            return []
        finally:
            db.close()

    def _fetch_inventory(self, inventory_ids: List[str]) -> List[Dict[str, Any]]:
        if not inventory_ids:
            return []
        from src.models.database import InventoryMetadata

        db = self._db_factory()
        try:
            rows = (
                db.query(InventoryMetadata)
                .filter(InventoryMetadata.id.in_(inventory_ids))
                .all()
            )
            return [
                {
                    "inventory_id": inv.id,
                    "publisher": inv.publisher,
                    "domain": inv.domain,
                    "ad_format": inv.ad_format,
                    "floor_price": inv.floor_price,
                    "viewability_rate": inv.viewability_rate,
                }
                for inv in rows
            ]
        except Exception:
            logger.warning("Failed to fetch inventory", exc_info=True)
            return []
        finally:
            db.close()
