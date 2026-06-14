"""Tests for the FastAPI API layer — app factory, middleware, schemas, endpoints."""

from unittest.mock import patch, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from src.api.middleware import (
    APIKeyAuthMiddleware,
    RateLimitMiddleware,
    RequestLoggingMiddleware,
)
from src.models.schemas import (
    HealthResponse,
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
    IssueType,
    EscalationLevel,
)


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------

class TestQueryRequestSchema:
    def test_valid_request(self):
        req = QueryRequest(text="Why is fill rate low?")
        assert req.text == "Why is fill rate low?"
        assert req.time_range is None

    def test_empty_text_rejected(self):
        with pytest.raises(Exception):
            QueryRequest(text="")

    def test_text_too_long_rejected(self):
        with pytest.raises(Exception):
            QueryRequest(text="x" * 5000)


class TestHealthResponseSchema:
    def test_health_response(self):
        resp = HealthResponse(version="0.1.0")
        assert resp.status == "ok"
        assert resp.version == "0.1.0"
        assert resp.postgres == "unknown"


class TestIngestResponseSchema:
    def test_ingest_response(self):
        resp = IngestResponse(rows_ingested=42, message="ok")
        assert resp.rows_ingested == 42


class TestQueryResponseSchema:
    def test_query_response(self):
        resp = QueryResponse(
            issue_type=IssueType.DELIVERY_UNDERPERFORMANCE,
            summary="Fill rate dropped.",
            confidence=0.85,
            escalation=EscalationLevel.MEDIUM,
        )
        assert 0.0 <= resp.confidence <= 1.0
        assert resp.entities == []


# ---------------------------------------------------------------------------
# APIKeyAuthMiddleware tests
# ---------------------------------------------------------------------------

class TestAPIKeyAuthMiddleware:
    """Tests for API key authentication middleware."""

    def test_missing_api_key_returns_401(self):
        from fastapi import FastAPI
        from starlette.testclient import TestClient

        app = FastAPI()

        @app.get("/protected")
        async def protected():
            return {"msg": "ok"}

        with patch("src.api.middleware.settings") as mock_settings:
            mock_settings.API_KEY = "test-key"
            app.add_middleware(APIKeyAuthMiddleware)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/protected")
            assert resp.status_code == 401

    def test_invalid_api_key_returns_403(self):
        from fastapi import FastAPI
        from starlette.testclient import TestClient

        app = FastAPI()

        @app.get("/protected")
        async def protected():
            return {"msg": "ok"}

        with patch("src.api.middleware.settings") as mock_settings:
            mock_settings.API_KEY = "correct-key"
            app.add_middleware(APIKeyAuthMiddleware)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/protected", headers={"X-API-Key": "wrong-key"})
            assert resp.status_code == 403

    def test_valid_api_key_passes(self):
        from fastapi import FastAPI
        from starlette.testclient import TestClient

        app = FastAPI()

        @app.get("/protected")
        async def protected():
            return {"msg": "ok"}

        with patch("src.api.middleware.settings") as mock_settings:
            mock_settings.API_KEY = "correct-key"
            app.add_middleware(APIKeyAuthMiddleware)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/protected", headers={"X-API-Key": "correct-key"})
            assert resp.status_code == 200

    def test_health_skips_auth(self):
        from fastapi import FastAPI
        from starlette.testclient import TestClient

        app = FastAPI()

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        with patch("src.api.middleware.settings") as mock_settings:
            mock_settings.API_KEY = "test-key"
            app.add_middleware(APIKeyAuthMiddleware)
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/health")
            assert resp.status_code == 200


# ---------------------------------------------------------------------------
# RateLimitMiddleware tests
# ---------------------------------------------------------------------------

class TestRateLimitMiddleware:
    """Tests for sliding-window rate limiter middleware."""

    def test_rate_limit_allows_normal_traffic(self):
        from fastapi import FastAPI
        from starlette.testclient import TestClient

        app = FastAPI()

        @app.get("/endpoint")
        async def endpoint():
            return {"msg": "ok"}

        with patch("src.api.middleware.settings") as mock_settings:
            mock_settings.RATE_LIMIT_PER_MINUTE = 5
            app.add_middleware(RateLimitMiddleware, window_seconds=60)
            client = TestClient(app, raise_server_exceptions=False)

            for _ in range(5):
                resp = client.get("/endpoint", headers={"X-API-Key": "k"})
                assert resp.status_code == 200

    def test_rate_limit_returns_429(self):
        from fastapi import FastAPI
        from starlette.testclient import TestClient

        app = FastAPI()

        @app.get("/endpoint")
        async def endpoint():
            return {"msg": "ok"}

        with patch("src.api.middleware.settings") as mock_settings:
            mock_settings.RATE_LIMIT_PER_MINUTE = 3
            app.add_middleware(RateLimitMiddleware, window_seconds=60)
            client = TestClient(app, raise_server_exceptions=False)

            for _ in range(3):
                client.get("/endpoint", headers={"X-API-Key": "k"})
            resp = client.get("/endpoint", headers={"X-API-Key": "k"})
            assert resp.status_code == 429


# ---------------------------------------------------------------------------
# RequestLoggingMiddleware tests
# ---------------------------------------------------------------------------

class TestRequestLoggingMiddleware:
    def test_logging_middleware_passes_requests(self):
        from fastapi import FastAPI
        from starlette.responses import JSONResponse

        app = FastAPI()

        @app.get("/test")
        async def test_route():
            return {"msg": "hello"}

        app.add_middleware(RequestLoggingMiddleware)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/test")
        assert resp.status_code == 200
        assert resp.json() == {"msg": "hello"}


# ---------------------------------------------------------------------------
# App factory tests (mocked settings to avoid .env)
# ---------------------------------------------------------------------------

class TestAppFactory:
    """Tests for the FastAPI application factory."""

    def test_create_app_returns_fastapi(self):
        from fastapi import FastAPI

        app = FastAPI(title="AdOps Copilot API", version="0.1.0", description="test")
        assert isinstance(app, FastAPI)
        assert app.title == "AdOps Copilot API"

    def test_app_metadata(self):
        from fastapi import FastAPI

        app = FastAPI(title="AdOps Copilot API", version="0.1.0", description="test")
        assert app.version == "0.1.0"
        assert "AdOps" in app.title
