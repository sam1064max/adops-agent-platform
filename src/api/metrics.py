"""Prometheus metrics definitions for the AdOps Agent Platform API."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

query_count = Counter(
    "adops_api_query_total",
    "Total number of /ask queries processed",
    ["issue_type", "status"],
)

ingest_count = Counter(
    "adops_api_ingest_total",
    "Total number of /ingest requests processed",
    ["data_type", "status"],
)

retrieval_latency = Histogram(
    "adops_retrieval_latency_seconds",
    "Time spent in RetrievalAgent (vector search + DB lookup)",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

analysis_latency = Histogram(
    "adops_analysis_latency_seconds",
    "Time spent in AnalysisAgent (root-cause + recommendation)",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

response_latency = Histogram(
    "adops_response_latency_seconds",
    "Time spent in ResponseAgent (synthesis + formatting)",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

qdrant_latency = Histogram(
    "adops_qdrant_latency_seconds",
    "Time spent on Qdrant vector-search operations",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

active_requests = Gauge(
    "adops_active_requests",
    "Number of requests currently being processed",
)

db_latency = Histogram(
    "adops_db_latency_seconds",
    "Time spent on PostgreSQL queries",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)

request_duration = Histogram(
    "adops_request_duration_seconds",
    "End-to-end request duration",
    ["method", "path", "status_code"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
