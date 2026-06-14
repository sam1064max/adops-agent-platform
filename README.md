# AdOps Agent Platform

[![CI](https://github.com/sushant-shambharkar/adops-agent-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/sushant-shambharkar/adops-agent-platform/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/sushant-shambharkar/adops-agent-platform)](https://github.com/sushant-shambharkar/adops-agent-platform/releases)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-compose-ready-blue.svg)](https://docs.docker.com/compose/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

An AI-powered AdOps troubleshooting copilot that helps Ad Operations teams diagnose delivery issues through Retrieval-Augmented Generation (RAG).

Built with a 2023-era technology stack: FastAPI, Qdrant, Sentence Transformers, SQLAlchemy, and Prometheus/Grafana observability.

---

## Architecture

```
                          ┌─────────────────────┐
                          │      User Query      │
                          └──────────┬──────────┘
                                     │
                          ┌──────────▼──────────┐
                          │   AdOps Copilot API  │
                          │      (FastAPI)       │
                          └──────────┬──────────┘
                                     │
              ┌──────────────────────┼──────────────────────┐
              │                      │                      │
   ┌──────────▼──────────┐ ┌────────▼────────┐ ┌──────────▼──────────┐
   │    Query Agent      │ │ Retrieval Agent │ │   Analysis Agent    │
   │  (Classification)   │ │  (RAG Search)   │ │  (Root Cause)       │
   └──────────┬──────────┘ └────────┬────────┘ └──────────┬──────────┘
              │                      │                      │
              │              ┌───────▼───────┐             │
              │              │  Qdrant + KB   │             │
              │              │  (Vector DB)   │             │
              │              └───────────────┘             │
              │                                            │
   ┌──────────▼────────────────────────────────────────────▼──┐
   │                  Response Agent                           │
   │              (Synthesis & Formatting)                     │
   └──────────────────────────┬───────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Structured Answer │
                    │  • Summary         │
                    │  • Root Cause      │
                    │  • Evidence        │
                    │  • Actions         │
                    │  • Escalation      │
                    └───────────────────┘
```

---

## Features

- **Natural Language Querying** — Ask questions in plain English about delivery issues
- **Automated Issue Classification** — Categorizes issues: fill rate, CTR, underdelivery, inventory, revenue, pacing
- **RAG-Powered Knowledge Base** — 10 expert troubleshooting guides for contextual answers
- **Root Cause Analysis** — Statistical anomaly detection and heuristic reasoning
- **Structured Responses** — Summary, evidence, root cause, confidence scores, recommended actions
- **Full Observability** — Prometheus metrics + Grafana dashboards
- **Production Ready** — Docker Compose, CI/CD, API authentication, rate limiting

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL (or use Docker)
- Qdrant (or use Docker)

### Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/sushant-shambharkar/adops-agent-platform.git
cd adops-agent-platform

# Copy environment config
cp .env.example .env

# Start all services
docker-compose up -d

# Seed the database
docker-compose exec api python scripts/init_db.py

# Ingest knowledge base into Qdrant
curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Content-Type: application/json" \
  -d '{"data_type": "knowledge_base", "payload": [{"source": "kb"}]}'
```

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Qdrant (or use Docker)
docker-compose up -d postgres qdrant

# Set environment variables
export POSTGRES_URL="postgresql+psycopg2://adops:adops@localhost:5432/adops"
export QDRANT_HOST="localhost"

# Seed database
python scripts/init_db.py

# Run the API
uvicorn src.api.app:app --host 0.0.0.0 --port 8000 --reload
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/ask` | Ask a natural language question |
| `POST` | `/api/v1/ingest` | Trigger RAG ingestion pipeline |
| `GET` | `/api/v1/campaign/{id}` | Get campaign metrics |
| `POST` | `/api/v1/campaigns` | List campaigns with filters |
| `GET` | `/api/v1/inventory/{id}` | Get inventory metadata |
| `POST` | `/api/v1/delivery-logs` | Query delivery logs |
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/metrics` | Prometheus metrics |

### Sample Query

```bash
curl -X POST http://localhost:8000/api/v1/ask \
  -H "Content-Type: application/json" \
  -d '{"text": "Why is campaign C101 underdelivering?"}'
```

**Response:**

```json
{
  "issue_type": "delivery_underperformance",
  "entities": ["101"],
  "summary": "Detected delivery underperformance. Campaign C101 pacing at 62% with fill rate dropped from 85% to 54%.",
  "evidence": [
    "[KB] Underdelivery typically caused by narrow targeting...",
    "[DB] Campaign C101 | impressions=310000 | status=active"
  ],
  "root_cause": "Inventory shortage in sports channels combined with narrow geo targeting.",
  "confidence": 0.84,
  "recommended_actions": [
    "Audit creative assets for fatigue and refresh if CTR has declined >20%.",
    "Verify pacing configuration aligns with flight dates.",
    "Check daily caps and frequency caps for over-restriction."
  ],
  "escalation": "low"
}
```

---

## Sample Queries

| Question | Issue Type |
|----------|------------|
| "Why is fill rate dropping in US inventory?" | fill_rate |
| "Why is campaign C101 underdelivering?" | underdelivery |
| "Why did CTR fall this week?" | ctr |
| "Why is sports inventory not serving?" | inventory |
| "What is causing low revenue yesterday?" | revenue |
| "Which campaigns are pacing behind target?" | pacing |
| "Why are impressions lower than expected?" | underdelivery |
| "What changed in delivery performance yesterday?" | general |

---

## Knowledge Base

The system includes 10 expert troubleshooting guides:

| Document | Coverage |
|----------|----------|
| `fill_rate_drop.md` | Fill rate diagnostics, demand issues, floor prices |
| `underdelivery.md` | Campaign pacing, targeting, bid competition |
| `ctr_drop.md` | Creative fatigue, audience mismatch, viewability |
| `inventory_not_serving.md` | Ad server config, tag errors, header bidding |
| `budget_exhaustion.md` | Budget caps, pacing, shared budgets |
| `frequency_cap.md` | Cross-device tracking, dedup windows |
| `geo_targeting.md` | IP geolocation, GDPR/CCPA, DMA targeting |
| `creative_rejection.md` | Ad review policies, specs, brand safety |
| `supply_shortage.md` | Forecasting, seasonal trends, floor prices |
| `auction_competitiveness.md` | Bid landscape, win rates, CPM inflation |

---

## Observability

### Prometheus Metrics

Available at `http://localhost:8000/api/v1/metrics`

- `adops_api_query_total` — Total queries processed
- `adops_retrieval_latency_seconds` — Retrieval agent latency
- `adops_analysis_latency_seconds` — Analysis agent latency
- `adops_response_latency_seconds` — Response agent latency
- `adops_qdrant_latency_seconds` — Qdrant search latency
- `adops_active_requests` — Active request count

### Grafana Dashboard

Access at `http://localhost:3000` (admin/admin)

Pre-configured dashboard with:
- Query volume over time
- Agent latency distributions
- Error rates
- Active requests

---

## Development

### Running Tests

```bash
pytest tests/ -v
```

### Linting

```bash
ruff check src/ tests/
ruff format --check src/ tests/
```

### Project Structure

```
adops-agent-platform/
├── src/
│   ├── agents/          # Query, Retrieval, Analysis, Response agents
│   ├── analytics/       # Fill rate, CTR, pacing, inventory analyzers
│   ├── api/             # FastAPI app, routes, middleware, dependencies
│   ├── config/          # Settings and configuration
│   ├── ingestion/       # RAG pipeline, document loader, embeddings
│   ├── models/          # SQLAlchemy ORM, Pydantic schemas
│   └── retrieval/       # (Extended retrieval logic)
├── knowledge_base/      # 10 troubleshooting markdown guides
├── datasets/            # Sample campaign, delivery, inventory data
├── tests/               # Pytest test suite
├── evaluation/          # Offline evaluation framework
├── dashboards/          # Grafana dashboard JSON
├── monitoring/          # Prometheus configuration
├── scripts/             # DB init, data seeding, evaluation runner
├── .github/workflows/   # CI/CD pipelines
├── Dockerfile
├── docker-compose.yml
├── Makefile
└── pyproject.toml
```

---

## Evaluation

Run the offline evaluation suite:

```bash
python scripts/run_eval.py
```

This generates `evaluation_report.html` with:
- Retrieval Precision
- Recall@K
- Context Relevance
- Answer Accuracy

---

## Tech Stack (2023)

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11, FastAPI, Pydantic |
| Database | PostgreSQL 15, SQLAlchemy |
| Vector DB | Qdrant |
| Embeddings | Sentence Transformers (all-MiniLM-L6-v2) |
| Analytics | Pandas, NumPy, Scikit-learn |
| Observability | Prometheus, Grafana |
| Containerization | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Testing | Pytest |

---

## Roadmap

- [ ] LLM integration (Llama 2 / GPT-4 fallback)
- [ ] Real-time alerting via Slack/webhooks
- [ ] Multi-tenant support
- [ ] Campaign simulation engine
- [ ] A/B testing framework for responses
- [ ] Historical trend dashboards
- [ ] Automated report generation

---

## License

MIT License — see [LICENSE](LICENSE) for details.
