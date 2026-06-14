# AdOps Agent Platform

[![CI](https://github.com/sam1064max/adops-agent-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/sam1064max/adops-agent-platform/actions/workflows/ci.yml)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-compose-ready-blue.svg)](https://docs.docker.com/compose/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

**Operational Intelligence Platform for Ad Delivery Diagnostics**

An AI-powered investigation system that helps Ad Operations teams diagnose delivery issues through automated root-cause analysis and evidence-driven reporting.

Built like an internal platform at Amagi, FreeWheel, Magnite, or Google Ad Manager (2023 era).

---

## Architecture

```
                  User Query
                      │
                      ▼
         Investigation Orchestrator
                      │
       ┌──────────────┼──────────────┐
       ▼              ▼              ▼
 Campaign Agent  Inventory Agent  Delivery Agent
       │              │              │
       ▼              ▼              ▼
  Campaign DB    Inventory DB    Delivery Logs
       │              │              │
       └──────────────┼──────────────┘
                      ▼
           Root Cause Engine
              (hypothesis → rank)
                      │
                      ▼
         Recommendation Engine
                      │
                      ▼
             Investigation Report
    • Summary        • Root Cause     • Confidence
    • Evidence       • Supporting     • Recommendations
    • Risk Level       Factors
```

The **investigation engine** drives answers — operational data contributes >80% of reasoning. KB retrieval is supplemental (<20%).

---

## Features

- **Automated Root-Cause Analysis** — Investigates delivery issues through evidence collection, hypothesis generation, and ranking
- **AdTech Analytics** — Fill rate, pacing, win rate, bid rate, eCPM, auction pressure, CTR, inventory health
- **Knowledge Graph** — Entity-relationship graph for Campaign, Inventory, Region, Device, Channel relationships
- **Trend Analysis** — 7/30-day trends, anomaly detection, change points, seasonality, linear forecasting
- **Investigation Pipeline** — Planner → Evidence Collector → Hypothesis Generator → Ranker → Root Cause → Recommendations
- **Operational Dashboards** — Internal FastAPI dashboards for campaign health, inventory health, risk explorer
- **Full Observability** — Prometheus metrics + Grafana dashboards
- **RAG-Enhanced** — KB retrieval supplements operational analysis (<20% contribution)

---

## Quick Start

```bash
git clone https://github.com/sam1064max/adops-agent-platform.git
cd adops-agent-platform
cp .env.example .env
docker-compose up -d
docker-compose exec api python scripts/init_db.py
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/ask` | Full investigation — primary endpoint |
| `POST` | `/api/v1/investigate` | Alias for `/ask` |
| `GET` | `/api/v1/campaign/{id}/investigate` | Investigate specific campaign |
| `POST` | `/api/v1/ingest` | Trigger RAG ingestion |
| `GET` | `/api/v1/campaign/{id}` | Campaign metrics |
| `POST` | `/api/v1/campaigns` | List campaigns |
| `GET` | `/api/v1/inventory/{id}` | Inventory metadata |
| `POST` | `/api/v1/delivery-logs` | Query delivery logs |
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/metrics` | Prometheus metrics |
| `GET` | `/dashboard/` | Operational summary dashboard |

---

## Sample Investigation

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"text": "Why is campaign C1004 underdelivering?"}'
```

**Response:**

```json
{
  "summary": "Campaign C1004 pacing at 62%. Primary cause: inventory shortage in Sports channels.",
  "primary_cause": "Inventory shortage - available supply decreased 38%",
  "confidence": 0.84,
  "evidence": [
    {"metric": "fill_rate", "current": 54, "historical": 85, "delta": -31},
    {"metric": "win_rate", "current": 42, "historical": 71, "delta": -29},
    {"metric": "pacing_ratio", "current": 0.62, "historical": 0.95, "delta": -0.33}
  ],
  "supporting_factors": [
    "Geo targeting constraints limiting available inventory",
    "Sports channel supply down 42%",
    "CTV inventory fill rate dropped 35%"
  ],
  "recommendations": [
    {"action": "Expand inventory pool to include adjacent channels", "priority": "high", "expected_impact": "+18% inventory availability"},
    {"action": "Relax geo targeting from DMA-level to state-level", "priority": "medium", "expected_impact": "+12% reach"},
    {"action": "Increase bid floor tolerance by 15%", "priority": "medium", "expected_impact": "+8% win rate"}
  ],
  "risk_level": "medium"
}
```

---

## Investigation Engine

The investigation pipeline transforms user questions into structured, evidence-driven reports.

1. **Planner** — Classifies issue type, extracts entities, generates investigation steps
2. **Evidence Collector** — Executes analytics modules against operational data
3. **Hypothesis Generator** — Forms hypotheses from evidence deltas (fill_rate drop >20% → inventory hypothesis)
4. **Hypothesis Ranker** — Scores by confidence + impact + evidence strength
5. **Root Cause Engine** — Determines primary cause with supporting factors
6. **Recommendation Engine** — Generates operational actions with expected impact

---

## AdTech Analytics

| Analyzer | Metrics | Detects |
|----------|---------|---------|
| Fill Rate | fill_rate, request_fill_rate, inventory_fill_rate | Supply shortage, request spikes, floor price issues |
| Pacing | pacing_ratio, forecast_completion, budget_consumption | Underdelivery, overdelivery, budget constraints |
| CTR | ctr, fatigue_score, audience_match | Creative fatigue, audience mismatch, position effects |
| Auction | bid_rate, win_rate, eCPM, auction_pressure | Competitive loss, bid landscape changes, floor price |
| Inventory | health_score, supply_trend, regional_availability | Inactive inventory, supply degradation, regional outages |

---

## Knowledge Graph

Entity types: Campaign, Inventory, Region, Device, Channel, Advertiser, ContentCategory, Issue

Relationships: TARGETS, USES, BELONGS_TO, LOCATED_IN, HAS_ADVERTISER, DEVICE_TYPE

Built with NetworkX. Supports impact tracing, campaign footprint analysis, regional issue detection.

---

## Documentation

| Document | Description |
|----------|-------------|
| `docs/Architecture.md` | Full system architecture and components |
| `docs/InvestigationEngine.md` | Investigation pipeline deep-dive |
| `docs/RootCauseEngine.md` | Root cause analysis methodology |
| `docs/AdTechMetrics.md` | AdTech metrics reference |
| `docs/KnowledgeGraph.md` | Knowledge graph schema and queries |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11, FastAPI, Pydantic |
| Database | PostgreSQL 15, SQLAlchemy |
| Vector DB | Qdrant |
| Embeddings | Sentence Transformers (all-MiniLM-L6-v2) |
| Analytics | Pandas, NumPy, Scikit-learn |
| Knowledge Graph | NetworkX |
| Observability | Prometheus, Grafana |
| Containerization | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Testing | Pytest |
