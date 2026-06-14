# AdOps Agent Platform — System Architecture

**Version:** 0.1.0 | **Status:** Active Development  
**Owner:** AdOps Engineering | **Last Updated:** 2026-06-14

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Component Descriptions](#3-component-descriptions)
4. [Data Flow](#4-data-flow)
5. [Tech Stack](#5-tech-stack)
6. [Deployment Architecture](#6-deployment-architecture)
7. [API Surface](#7-api-surface)
8. [Observability](#8-observability)
9. [Security](#9-security)

---

## 1. System Overview

The AdOps Agent Platform is an AI-powered operational intelligence system for programmatic advertising operations. It ingests structured delivery data, maintains a knowledge base of ad operations documentation, and runs a multi-agent pipeline that classifies issues, retrieves relevant context, performs root-cause analysis, and generates plain-language responses with recommended actions.

**Core capabilities:**

- **Agent pipeline**: Classify → Retrieve → Analyse → Respond
- **RAG ingestion**: Document loading, chunking, embedding, and vector storage
- **Analytics engine**: Fill rate, pacing, CTR, and inventory health analyzers
- **Knowledge graph**: Entity relationship mapping for impact tracing
- **Internal dashboards**: HTML operational pages for monitoring and exploration

---

## 2. Architecture Diagram

```
                                    ┌──────────────────────┐
                                    │   External Systems    │
                                    │  (DSPs, SSPs, Ad     │
                                    │   Servers, Logs)     │
                                    └──────────┬───────────┘
                                               │
                                    ┌──────────▼───────────┐
                                    │   Ingestion Pipeline  │
                                    │                      │
                                    │  Document Loader ────│──┐
                                    │       │               │  │
                                    │       ▼               │  │
                                    │  Chunker             │  │
                                    │       │               │  │
                                    │       ▼               │  │
                                    │  Embedder            │  │
                                    │  (SentenceTransformer)│  │
                                    │       │               │  │
                                    │       ▼               │  │
                                    │  Vector Store         │  │
                                    │  (Qdrant)             │  │
                                    └──────────┬───────────┘  │
                                               │              │
                    ┌──────────────────────────┼──────────────┘
                    │                          │
                    ▼                          ▼
          ┌──────────────────┐      ┌──────────────────┐
          │   Qdrant (VecDB) │      │  PostgreSQL (OLTP)│
          │  - embeddings    │      │  - campaigns      │
          │  - metadata      │      │  - delivery_logs  │
          │  - hybrid search │      │  - inventory      │
          └────────┬─────────┘      └────────┬─────────┘
                   │                         │
                   └──────┬──────────────────┘
                          │
                          ▼
          ┌──────────────────────────────────────┐
          │         Agent Pipeline               │
          │                                      │
          │  ┌──────────┐  ┌────────────┐        │
          │  │ Query    │  │ Retrieval  │        │
          │  │ Agent    │──┤ Agent      │        │
          │  │ (classify)│  │ (search+DB)│        │
          │  └──────────┘  └──────┬─────┘        │
          │                       │              │
          │                 ┌─────▼──────┐       │
          │                 │ Analysis   │       │
          │                 │ Agent      │       │
          │                 │ (root cause)│      │
          │                 └─────┬──────┘       │
          │                       │              │
          │                 ┌─────▼──────┐       │
          │                 │ Response   │       │
          │                 │ Agent      │       │
          │                 │ (format)   │       │
          │                 └───────────┘       │
          └──────────────────────────────────────┘
                          │
                          ▼
          ┌──────────────────────────────────────┐
          │           FastAPI Server             │
          │                                      │
          │  ┌──────────┐  ┌──────────────────┐ │
          │  │ API      │  │ Dashboard Pages   │ │
          │  │ /api/v1/ │  │ /dashboard/*      │ │
          │  │ - /ask   │  │ (HTML dark theme) │ │
          │  │ - /ingest│  └──────────────────┘ │
          │  │ - /health│                       │
          │  └──────────┘                       │
          └──────────────────────────────────────┘
                          │
                          ▼
          ┌──────────────────────────────────────┐
          │          Analytics Modules           │
          │                                      │
          │  FillRateAnalyzer  PacingAnalyzer    │
          │  CTRAnalyzer       InventoryAnalyzer │
          └──────────────────────────────────────┘
```

### Investigation Pipeline Flow

```
User Query (natural language)
        │
        ▼
┌──────────────────────────────────────────────────┐
│ Stage 1: QueryAgent.classify_issue()             │
│   - Detect issue type (keyword scoring)          │
│   - Extract entities (campaign/inventory IDs)    │
│   - Resolve time range (relative/absolute dates) │
│   Output: issue_type, entities[], time_range     │
└──────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────┐
│ Stage 2: RetrievalAgent.retrieve()               │
│   - Embed query text (SentenceTransformer)       │
│   - Vector search in Qdrant (top-k snippets)     │
│   - Fetch campaign + inventory from PostgreSQL   │
│   Output: snippets[], campaign_context[],         │
│            inventory_context[]                    │
└──────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────┐
│ Stage 3: AnalysisAgent.analyse()                 │
│   - Collect evidence from snippets + DB context  │
│   - Infer root cause from issue type + evidence   │
│   - Compute confidence score (0-1)               │
│   - Map recommended actions by issue type        │
│   Output: root_cause, confidence, actions[],      │
│            evidence[]                             │
└──────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────┐
│ Stage 4: ResponseAgent.synthesise()              │
│   - Determine escalation level (LOW→CRITICAL)    │
│   - Build plain-language summary                 │
│   - Package as QueryResponse schema              │
│   Output: QueryResponse (summary, root_cause,    │
│            confidence, actions, escalation)       │
└──────────────────────────────────────────────────┘
        │
        ▼
   JSON Response to User
```

---

## 3. Component Descriptions

### 3.1 Ingestion Pipeline (`src/ingestion/`)

| Component | File | Responsibility |
|-----------|------|----------------|
| `DocumentLoader` | `document_loader.py` | Loads documents from knowledge base directory, splits into chunks with overlap |
| `Embedder` | `embedder.py` | Wraps SentenceTransformer; provides `embed()` and `embed_batch()` |
| `VectorStore` | `vector_store.py` | Qdrant client abstraction; handles collection, upsert, and search |
| `IngestionPipeline` | `pipeline.py` | Orchestrator: load → chunk → embed → store |

### 3.2 Agent Pipeline (`src/agents/`)

| Component | File | Responsibility |
|-----------|------|----------------|
| `QueryAgent` | `query_agent.py` | Keyword-based issue classification, entity extraction, time-range resolution |
| `RetrievalAgent` | `retrieval_agent.py` | Embed query → vector search in Qdrant → enrich with Postgres data |
| `AnalysisAgent` | `analysis_agent.py` | Evidence collection, heuristic root cause inference, confidence scoring |
| `ResponseAgent` | `response_agent.py` | Escalation assignment, summary generation, response formatting |

### 3.3 Analytics Modules (`src/analytics/`)

| Module | File | Key Classes |
|--------|------|-------------|
| Fill Rate | `fill_rate_analyzer.py` | `FillRateAnalyzer` — calculates fill rates, detects drops, identifies inventory shortages, finds request spikes |
| Pacing | `pacing_analyzer.py` | `PacingAnalyzer` — pacing ratios, under/over delivery detection, budget burn projections |
| CTR | `ctr_analyzer.py` | `CTRAnalyzer` — CTR trends, creative fatigue detection, audience mismatch, inventory quality scoring |
| Inventory | `inventory_analyzer.py` | `InventoryAnalyzer` — health scoring, inactive/drop detection, regional analysis |

### 3.4 Knowledge Graph (`src/knowledge_graph/`)

[Planned] Entity relationship store linking campaigns, inventory sources, creatives, publishers, and geos for impact tracing and path analysis.

### 3.5 Investigation Engine (`src/investigation/`)

[Planned] Multi-step investigation workflow orchestrator that builds on the agent pipeline to provide structured investigation reports, hypothesis ranking, and root cause determination with evidence chains.

### 3.6 API & Dashboards (`src/api/`, `src/dashboards/`)

| Component | Path | Description |
|-----------|------|-------------|
| REST API | `/api/v1/*` | Agent pipeline, data queries, health, metrics |
| Dashboards | `/dashboard/*` | HTML operational pages (dark theme, inline CSS) |
| Health | `/api/v1/health` | Qdrant + PostgreSQL status |
| Metrics | `/api/v1/metrics` | Prometheus `/metrics` endpoint |

---

## 4. Data Flow

### 4.1 Ingestion Flow

```
External Data ──→ Document Loader ──→ Chunker ──→ Embedder ──→ Qdrant
                                                              │
                                                    PostgreSQL (metadata)
```

### 4.2 Query Flow

```
User Request ──→ QueryAgent ──→ RetrievalAgent ──→ AnalysisAgent ──→ ResponseAgent
                     │               │                  │                  │
                     ▼               ▼                  ▼                  ▼
              classify issue   search Qdrant +    infer root cause    build response
              extract entities  query Postgres    score confidence    assign escalation
```

### 4.3 Data Sources

| Source | Type | Tables | Accessed By |
|--------|------|--------|-------------|
| PostgreSQL | Relational | `campaigns`, `delivery_logs`, `inventory_metadata` | Agents, Analytics, Dashboards |
| Qdrant | Vector DB | `adops_knowledge` (collection) | RetrievalAgent |

---

## 5. Tech Stack

### 5.1 Runtime & Framework

| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.10+ | Primary language |
| FastAPI | 0.104+ | HTTP API framework |
| Uvicorn | 0.24+ | ASGI server |
| Pydantic | 2.x | Schema validation |
| SQLAlchemy | 2.0+ | ORM / database access |

### 5.2 Storage

| Technology | Purpose |
|-----------|---------|
| PostgreSQL 15+ | Operational data store (campaigns, delivery logs, inventory) |
| Qdrant | Vector similarity search for RAG knowledge base |

### 5.3 AI/ML

| Technology | Purpose |
|-----------|---------|
| SentenceTransformers | Text embedding generation (`all-MiniLM-L6-v2`) |
| Keyword-based classifier | Issue type detection (fallback / offline mode) |

### 5.4 Observability

| Technology | Purpose |
|-----------|---------|
| Prometheus Client | Metrics exposition (latency histograms, counters, gauges) |
| Python logging | Structured log output |

### 5.5 Development

| Technology | Purpose |
|-----------|---------|
| pytest | Unit and integration testing |
| pandas, numpy | Analytics computation |
| ruff | Python linting |
| mypy | Type checking |

---

## 6. Deployment Architecture

### 6.1 Container Layout

```
┌──────────────────────────────────────────────┐
│                    Docker                     │
│  ┌────────────────────────────────────────┐  │
│  │  adops-api (FastAPI + Uvicorn)        │  │
│  │  :8000                                 │  │
│  │  - Agent pipeline handlers             │  │
│  │  - Analytics modules                   │  │
│  │  - Dashboard pages                     │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────┐  ┌─────────────┐ │
│  │  PostgreSQL 15         │  │  Qdrant     │ │
│  │  :5432                 │  │  :6333      │ │
│  │  (campaigns, logs,     │  │  (vectors)  │ │
│  │   inventory)           │  │             │ │
│  └────────────────────────┘  └─────────────┘ │
└──────────────────────────────────────────────┘
```

### 6.2 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QDRANT_HOST` | localhost | Qdrant hostname |
| `QDRANT_PORT` | 6333 | Qdrant gRPC/HTTP port |
| `QDRANT_COLLECTION` | adops_knowledge | Collection name |
| `POSTGRES_URL` | postgresql+psycopg2://adops:adops@localhost:5432/adops | SQLAlchemy connection string |
| `API_KEY` | changeme | Bearer token for API auth |
| `RATE_LIMIT_PER_MINUTE` | 60 | Max requests per minute |
| `LOG_LEVEL` | INFO | Python log level |
| `EMBEDDING_MODEL` | all-MiniLM-L6-v2 | SentenceTransformer model |

### 6.3 Scaling Considerations

- **Agent pipeline** is stateless — scales horizontally behind a load balancer
- **Qdrant** supports replication and sharding for larger vector collections
- **PostgreSQL** can be read-replicated for analytics query offloading
- **Rate limiting** uses in-memory state — switch to Redis for multi-worker deployments

---

## 7. API Surface

### REST Endpoints (`/api/v1`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/ask` | Run full agent pipeline |
| POST | `/ingest` | Ingest data into vector store |
| GET | `/campaign/{id}` | Get single campaign |
| POST | `/campaigns` | List campaigns with filters |
| GET | `/inventory/{id}` | Get single inventory source |
| POST | `/delivery-logs` | Query delivery logs |
| GET | `/health` | System health check |
| GET | `/metrics` | Prometheus metrics |

### Dashboard Pages (`/dashboard`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/dashboard/` | Operational summary |
| GET | `/dashboard/campaigns` | Campaign health table |
| GET | `/dashboard/campaign/{id}` | Campaign detail with pacing, fill, win rates |
| GET | `/dashboard/inventory` | Inventory health table |
| GET | `/dashboard/inventory/{id}` | Inventory detail |
| GET | `/dashboard/risks` | Top risks list |
| GET | `/dashboard/anomalies` | Anomaly explorer |

---

## 8. Observability

### Metrics (Prometheus)

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `adops_api_query_total` | Counter | issue_type, status | Query count |
| `adops_api_ingest_total` | Counter | data_type, status | Ingestion count |
| `adops_retrieval_latency_seconds` | Histogram | — | Retrieval duration |
| `adops_analysis_latency_seconds` | Histogram | — | Analysis duration |
| `adops_response_latency_seconds` | Histogram | — | Response synthesis duration |
| `adops_qdrant_latency_seconds` | Histogram | — | Qdrant search latency |
| `adops_db_latency_seconds` | Histogram | — | PostgreSQL query latency |
| `adops_request_duration_seconds` | Histogram | method, path, status_code | Full request duration |
| `adops_active_requests` | Gauge | — | Concurrent request count |

### Logging

- Structured JSON logs via standard `logging` module
- Middleware logs every request with method, path, status, duration, client IP
- Agent pipeline logs each stage with latency and result summary

---

## 9. Security

- **API key authentication** via `X-API-Key` header (constant-time comparison)
- **Rate limiting** per API key (configurable window, in-memory)
- **Dashboard routes** are unprotected by default (intended for internal network)
- **No secrets in code** — all configuration via environment variables
- **CORS** is permissive by default (configure for production)
- **Input validation** via Pydantic schemas on all public endpoints
- **SQL injection** prevented via SQLAlchemy ORM parameterised queries

---

*This document is maintained by the AdOps Engineering team. For questions, contact #adops-platform.*
