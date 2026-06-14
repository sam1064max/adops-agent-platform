"""Dependency injection for the AdOps Agent Platform API.

All shared resources (DB sessions, vector clients, models, agents) are
managed as module-level singletons initialised lazily on first use.
"""

from __future__ import annotations

import logging
from typing import Optional

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.models.database import SessionLocal
from src.agents.query_agent import QueryAgent

logger = logging.getLogger(__name__)

# ── Singleton state ──────────────────────────────────────────────────────────

_qdrant_client: Optional[QdrantClient] = None
_embedding_model: Optional[SentenceTransformer] = None
_query_agent: Optional[QueryAgent] = None
_retrieval_agent: Optional["RetrievalAgent"] = None
_analysis_agent: Optional["AnalysisAgent"] = None
_response_agent: Optional["ResponseAgent"] = None


# ── Settings ─────────────────────────────────────────────────────────────────

def get_settings():
    """Return the global Settings instance."""
    return settings


# ── Qdrant ───────────────────────────────────────────────────────────────────

def get_qdrant_client() -> QdrantClient:
    """Return a lazily-initialised QdrantClient singleton."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
        logger.info(
            "Qdrant client connected to %s:%s",
            settings.QDRANT_HOST,
            settings.QDRANT_PORT,
        )
    return _qdrant_client


# ── PostgreSQL ───────────────────────────────────────────────────────────────

def get_db():
    """FastAPI dependency that yields a SQLAlchemy session and cleans up."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Embedding model ─────────────────────────────────────────────────────────

def get_embedding_model() -> SentenceTransformer:
    """Return a lazily-loaded SentenceTransformer singleton."""
    global _embedding_model
    if _embedding_model is None:
        logger.info("Loading embedding model: %s", settings.EMBEDDING_MODEL)
        _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info("Embedding model ready")
    return _embedding_model


# ── Agents ───────────────────────────────────────────────────────────────────

def get_query_agent() -> QueryAgent:
    """Return the QueryAgent singleton."""
    global _query_agent
    if _query_agent is None:
        _query_agent = QueryAgent()
    return _query_agent


def get_retrieval_agent():
    """Return the RetrievalAgent singleton, creating it on demand."""
    global _retrieval_agent
    if _retrieval_agent is None:
        from src.agents.retrieval_agent import RetrievalAgent

        _retrieval_agent = RetrievalAgent(
            qdrant_client=get_qdrant_client(),
            embedding_model=get_embedding_model(),
            db_session_factory=SessionLocal,
        )
    return _retrieval_agent


def get_analysis_agent():
    """Return the AnalysisAgent singleton, creating it on demand."""
    global _analysis_agent
    if _analysis_agent is None:
        from src.agents.analysis_agent import AnalysisAgent

        _analysis_agent = AnalysisAgent(
            db_session_factory=SessionLocal,
        )
    return _analysis_agent


def get_response_agent():
    """Return the ResponseAgent singleton, creating it on demand."""
    global _response_agent
    if _response_agent is None:
        from src.agents.response_agent import ResponseAgent

        _response_agent = ResponseAgent()
    return _response_agent


# ── Lifecycle helpers (called from lifespan) ──────────────────────────────────

def init_connections() -> None:
    """Warm up Qdrant and embedding model at startup."""
    logger.info("Initialising connections ...")
    get_qdrant_client()
    get_embedding_model()
    logger.info("Connections ready")


def close_connections() -> None:
    """Tear down connections at shutdown."""
    global _qdrant_client, _embedding_model
    if _qdrant_client is not None:
        try:
            _qdrant_client.close()
        except Exception:
            logger.warning("Error closing Qdrant client", exc_info=True)
        _qdrant_client = None

    _embedding_model = None
    logger.info("Connections closed")
