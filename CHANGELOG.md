# Changelog

All notable changes to the AdOps Agent Platform will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Full project scaffolding and repository structure
- FastAPI application with middleware, CORS, and lifecycle management
- Query Agent — classifies AdOps issues and extracts entities
- Retrieval Agent — Qdrant vector search + PostgreSQL enrichment
- Analysis Agent — root cause detection with heuristic reasoning
- Response Agent — structured answer synthesis with escalation logic
- RAG ingestion pipeline — document loading, chunking, embedding, Qdrant storage
- Analytics engines — fill rate, CTR, pacing, inventory analyzers
- Knowledge base — 10 expert troubleshooting guides
- Sample datasets — 30 campaigns, 500 delivery logs, 20 inventory sources
- Evaluation framework with HTML report generation
- Prometheus metrics and Grafana dashboard
- Docker Compose setup (API, PostgreSQL, Qdrant, Prometheus, Grafana)
- CI/CD pipeline with lint, test, security, and Docker build
- Release workflow with semantic versioning
- Comprehensive test suite (agents, analytics, ingestion, API)
- Database seeding and initialization scripts

## [0.1.0-alpha] - 2023-11-01

### Added
- Initial alpha release
- Core agent pipeline (Query → Retrieval → Analysis → Response)
- FastAPI endpoints (/ask, /health, /campaign, /inventory)
- Qdrant integration for knowledge base retrieval
- Sentence Transformer embeddings (all-MiniLM-L6-v2)
- Basic analytics modules
- Docker Compose configuration
- CI/CD with GitHub Actions

## [0.2.0-alpha] - 2023-11-15

### Added
- RAG ingestion pipeline with document chunking
- 10 comprehensive knowledge base articles
- Enhanced entity extraction (campaign IDs, inventory IDs, dates)
- Time range resolution (yesterday, this week, last 30 days, etc.)
- Prometheus metrics instrumentation
- Grafana dashboard with 7 panels

### Changed
- Improved issue classification with keyword scoring
- Better error handling across all agents

## [0.3.0-beta] - 2023-12-01

### Added
- Offline evaluation framework
- Sample dataset generation (campaigns, delivery logs, inventory)
- API rate limiting and key authentication middleware
- Request logging middleware
- Database seeding scripts

### Fixed
- Query agent entity extraction edge cases
- Retrieval agent filter construction

## [0.4.0-beta] - 2023-12-15

### Added
- Comprehensive test suite
- CI pipeline with lint, test, security, and Docker jobs
- Release pipeline with semantic versioning
- CHANGELOG.md

### Changed
- Refactored dependency injection for testability
- Improved response formatting with evidence-based summaries

## [1.0.0] - 2024-01-01

### Added
- Production-ready release
- Full documentation
- Evaluation results
- Performance benchmarks

### Changed
- Stabilized agent pipeline interfaces
- Hardened API security

---

## Version History

| Version | Date | Status |
|---------|------|--------|
| v0.1.0-alpha | Nov 2023 | Alpha |
| v0.2.0-alpha | Nov 2023 | Alpha |
| v0.3.0-beta | Dec 2023 | Beta |
| v0.4.0-beta | Dec 2023 | Beta |
| v1.0.0 | Jan 2024 | Stable |
