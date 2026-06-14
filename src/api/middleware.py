"""Middleware classes for the AdOps Agent Platform API."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Dict, List, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.config.settings import settings
from src.api.metrics import request_duration

logger = logging.getLogger(__name__)


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Validates the X-API-Key header against the configured API key.

    Skips health-check and metrics endpoints so liveness probes work
    without credentials.
    """

    SKIP_PATHS: frozenset = frozenset({"/health", "/metrics"})

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        if path in self.SKIP_PATHS:
            return await call_next(request)

        provided = request.headers.get("X-API-Key")
        if provided is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing X-API-Key header"},
            )

        if not self._constant_time_eq(provided, settings.API_KEY):
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid API key"},
            )

        return await call_next(request)

    @staticmethod
    def _constant_time_eq(a: str, b: str) -> bool:
        """Constant-time string comparison to prevent timing attacks."""
        if len(a) != len(b):
            return False
        result = 0
        for x, y in zip(a, b):
            result |= ord(x) ^ ord(y)
        return result == 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter keyed on X-API-Key.

    Uses a simple in-memory store with per-key buckets. Suitable for
    single-process deployments; use Redis for multi-worker setups.
    """

    def __init__(self, app=None, window_seconds: int = 60) -> None:
        super().__init__(app)
        self._window = window_seconds
        # key -> list of timestamps (seconds since epoch)
        self._hits: Dict[str, List[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path in APIKeyAuthMiddleware.SKIP_PATHS:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "anonymous")
        key = f"{api_key}:{request.client.host if request.client else 'unknown'}"

        now = time.monotonic()
        window_start = now - self._window

        # Prune old entries
        timestamps = self._hits[key]
        self._hits[key] = [t for t in timestamps if t > window_start]

        if len(self._hits[key]) >= settings.RATE_LIMIT_PER_MINUTE:
            retry_after = int(self._window - (now - self._hits[key][0]))
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": max(retry_after, 1),
                },
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        self._hits[key].append(now)
        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every request with method, path, status code, and duration."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "request failed | method=%s path=%s duration=%.1fms error=%s",
                request.method,
                request.url.path,
                duration_ms,
                exc,
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        status = response.status_code
        log_fn = logger.warning if status >= 500 else logger.info
        log_fn(
            "request | method=%s path=%s status=%d duration=%.1fms client=%s",
            request.method,
            request.url.path,
            status,
            duration_ms,
            client_ip,
        )

        request_duration.labels(
            method=request.method,
            path=request.url.path,
            status_code=str(status),
        ).observe(duration_ms / 1000.0)

        return response
