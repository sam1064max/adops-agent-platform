# Investigation Engine — AdOps Agent Platform

**Version:** 0.1.0 | **Status:** Active Development  
**Last Updated:** 2026-06-14

---

## Table of Contents

1. [Overview](#1-overview)
2. [How Investigations Work](#2-how-investigations-work)
3. [Planner Component](#3-planner-component)
4. [Evidence Collection](#4-evidence-collection)
5. [Hypothesis Generation and Ranking](#5-hypothesis-generation-and-ranking)
6. [Root Cause Determination](#6-root-cause-determination)
7. [Report Generation](#7-report-generation)
8. [Example Walkthrough](#8-example-walkthrough)
9. [API Reference](#9-api-reference)

---

## 1. Overview

The Investigation Engine is the core reasoning layer of the AdOps Agent Platform. It transforms raw operational data and natural-language user queries into structured, evidence-backed investigation reports with identified root causes, confidence scores, and recommended remediation actions.

The engine is built as a pipeline of specialised agents, each responsible for one phase of the investigation lifecycle:

```
User Query
    │
    ▼
┌──────────────────┐
│  1. Classify     │  QueryAgent — determine issue type, extract entities
└──────────────────┘
    │
    ▼
┌──────────────────┐
│  2. Retrieve     │  RetrievalAgent — gather evidence from vector DB + relational store
└──────────────────┘
    │
    ▼
┌──────────────────┐
│  3. Analyse      │  AnalysisAgent — infer root cause, compute confidence
└──────────────────┘
    │
    ▼
┌──────────────────┐
│  4. Synthesise   │  ResponseAgent — format results, assign escalation level
└──────────────────┘
    │
    ▼
 Structured Report
```

The engine operates in two modes:

| Mode | Description | When Used |
|------|-------------|-----------|
| **Interactive** | Full pipeline triggered via `POST /api/v1/ask` | User-submitted queries via API |
| **Automated** | Scheduled sweep of metrics to detect anomalies | Monitoring / alerting workflows |

---

## 2. How Investigations Work

### 2.1 Trigger Conditions

An investigation begins when:

1. A user submits a natural-language query via `POST /api/v1/ask`
2. An automated monitor detects metric thresholds being breached (planned)
3. A dashboard anomaly is clicked for deeper drill-down (planned)

### 2.2 Pipeline Execution

Each stage produces structured output that feeds into the next:

```
Stage                  Input                          Output
─────                  ─────                          ──────
QueryAgent             raw text string                issue_type, entities[], time_range
RetrievalAgent         issue_type, entities[]          snippets[], campaign_context[], inventory_context[]
AnalysisAgent          issue_type, entities[],         root_cause, confidence, evidence[], actions[]
                       retrieval_context
ResponseAgent          analysis + classification       QueryResponse (final report)
```

### 2.3 State Management

The pipeline is currently stateless — each request runs independently. Future versions will persist investigation state to PostgreSQL for history, replay, and collaborative review.

---

## 3. Planner Component

### 3.1 Role

The Planner (currently embedded in `QueryAgent.classify_issue()`) determines what kind of investigation to run and which data sources to prioritise.

### 3.2 Classification Method

The planner uses keyword-based scoring against predefined issue categories:

```python
KEYWORD_MAP = {
    "fill_rate": ["fill rate", "low fill", "fill dropped", "unfilled", "no fill"],
    "ctr": ["ctr", "click-through", "low clicks", "ctr drop"],
    "underdelivery": ["underdeliver", "not delivering", "slow delivery"],
    "inventory": ["inventory", "ad unit", "publisher", "supply"],
    "revenue": ["revenue", "rpm", "earnings", "revenue drop"],
    "pacing": ["pacing", "over pace", "under pace", "budget pace"],
}
```

Each keyword match increments a category score. The category with the highest score wins. Ties and zero scores default to `"general"`.

### 3.3 Entity Extraction

Entities are extracted via regex patterns:

| Entity Type | Pattern | Example |
|-------------|---------|---------|
| Campaign ID | `C\d{3,10}` | `C0042` |
| Inventory ID | `(inv\|inventory\|adunit)[_ -]\d{3,10}` | `inv_042` |
| Numeric IDs | `(campaign\|advertiser\|order)[#:\s]\d{4,10}` | `campaign #1234` |

### 3.4 Time Range Resolution

The planner resolves both relative and absolute time references:

| Query Phrase | Resolved Range |
|-------------|----------------|
| `"yesterday"` | Single date (T-1) |
| `"last 7 days"` | 7-day trailing window |
| `"last month"` | Previous calendar month |
| `"2026-06-01"` | Single specific date |
| `"06/01 to 06/14"` | Custom date range |
| *Default* | Last 7 days |

### 3.5 Planner Output

```json
{
    "issue_type": "fill_rate",
    "entities": [
        {"type": "campaign_id", "value": "0042", "raw_text": "C0042"},
        {"type": "inventory_id", "value": "042", "raw_text": "inv_042"}
    ],
    "time_range": {
        "start": "2026-06-07",
        "end": "2026-06-14",
        "relative": "last_7_days"
    }
}
```

---

## 4. Evidence Collection

### 4.1 Sources

Evidence is collected from two primary sources:

| Source | Contents | Query Method |
|--------|----------|-------------|
| **Qdrant vector store** | Knowledge base chunks (docs, SOPs, historical reports) | Semantic similarity search on embedded query |
| **PostgreSQL** | Campaign records, delivery logs, inventory metadata | SQLAlchemy ORM queries by entity ID |

### 4.2 Retrieval Process

```
Query text
    │
    ├─→ Encode with SentenceTransformer ──→ embedding vector
    │                                            │
    │                                     Qdrant search (top_k=10)
    │                                            │
    │                                     Return snippets[] with scores
    │
    ├─→ Extract campaign_ids, inventory_ids from entities
    │                                            │
    │                                     PostgreSQL lookup
    │                                            │
    │                                     Return campaign_context[]
    │                                     Return inventory_context[]
    │
    ▼
RetrievalAgent output (combined context)
```

### 4.3 Evidence Formatting

The `AnalysisAgent._collect_evidence()` method formats all retrieved data into a flat list of evidence strings:

```
[KB] Knowledge base chunk excerpt (truncated to 300 chars)
[DB] Campaign C0042 | "Summer Sale" | impressions=150000 | clicks=3200 | status=active
[DB] Inventory inv_042 | publisher=PubMatic | viewability_rate=0.72 | floor_price=0.45
```

Each evidence string is tagged with its source (`[KB]` or `[DB]`) for provenance tracking.

### 4.4 Evidence Limits

| Parameter | Default | Description |
|-----------|---------|-------------|
| `top_k` | 10 | Max Qdrant results |
| Snippet length | 300 chars | Truncation limit per snippet |
| Campaign context | Unbounded | All matches for extracted IDs |
| Inventory context | Unbounded | All matches for extracted IDs |

---

## 5. Hypothesis Generation and Ranking

### 5.1 Hypothesis Generation

Currently, the engine uses a deterministic mapping from issue type to root cause hypothesis. Each issue type maps to a primary hypothesis derived from the `_ACTION_MAP`:

| Issue Type | Primary Hypothesis |
|------------|-------------------|
| `delivery_underperformance` | Creative fatigue or pacing misconfiguration |
| `pacing_anomaly` | Bid strategy or budget allocation issue |
| `fraud_signal` | Invalid traffic detected |
| `inventory_shortage` | Insufficient supply from targeted sources |
| `creative_fatigue` | CTR decline from overexposure |
| `budget_depletion` | Spend rate exceeding plan |
| `geo_mismatch` | Targeting-audience misalignment |
| `viewability_drop` | Low-quality placements consuming budget |
| `brand_safety` | Content adjacency risk detected |

### 5.2 Ranking

The engine currently provides a single hypothesis per investigation. The confidence score serves as the ranking metric:

| Confidence Range | Interpretation |
|-----------------|----------------|
| 0.00 – 0.49 | Low confidence — manual review recommended |
| 0.50 – 0.74 | Medium confidence — supporting evidence found |
| 0.75 – 0.89 | High confidence — multiple evidence sources agree |
| 0.90 – 1.00 | Very high confidence — strong signal across all data |

### 5.3 Future: Multi-Hypothesis Ranking

The planned architecture supports comparing multiple hypotheses:

```
Hypothesis A: "Low fill rate due to inventory shortage"
    Evidence: [inv_042 fill rate dropped 40%, ad_requests stable]
    Score: 0.82

Hypothesis B: "Low fill rate due to floor price mismatch"
    Evidence: [floor price $0.45, market rate $0.30, bid volume down]
    Score: 0.65

Hypothesis C: "Low fill rate due to creative rejection"
    Evidence: [no creative rejection logs, CTR stable]
    Score: 0.12

→ Selected: Hypothesis A (highest score)
```

---

## 6. Root Cause Determination

### 6.1 Current Approach

Root cause is determined by the `AnalysisAgent._infer_root_cause()` method:

1. Look up the primary action/hypothesis from `_ACTION_MAP` based on issue type
2. Find the first `[DB]`-tagged evidence string for data grounding
3. Concatenate: `"{primary_hypothesis} Based on data: {evidence}"`

### 6.2 Confidence Scoring

Confidence is computed via `AnalysisAgent._compute_confidence()`:

```python
score = 0.3                      # Base confidence
if issue_type != "general":
    score += 0.2                  # Specific issue type bonus
score += min(len(evidence) * 0.05, 0.3)   # Evidence volume (up to 6 items)
score += min(len(campaigns) * 0.1, 0.2)    # Campaign data available (up to 2)
return min(score, 1.0)
```

| Factor | Max Contribution | Rationale |
|--------|-----------------|-----------|
| Base | 0.30 | Default starting point |
| Specific issue type | 0.20 | Non-general issues have stronger signal |
| Evidence count | 0.30 | More evidence = higher confidence (capped at 6 items) |
| Campaign data | 0.20 | Direct campaign context increases reliability |

### 6.3 Evidence Weighting

Future implementations will use weighted evidence scoring:

| Evidence Type | Weight | Example |
|--------------|--------|---------|
| Direct metric match | 0.35 | "fill_rate dropped 40%" |
| Temporal correlation | 0.25 | "drop coincided with creative rotation" |
| Entity relationship | 0.20 | "inventory C supplies campaign A" |
| Historical precedent | 0.15 | "similar issue resolved by bid adjustment" |
| External signal | 0.05 | "publisher reported SSP outage" |

---

## 7. Report Generation

### 7.1 Response Synthesis

The `ResponseAgent.synthesise()` method packages analysis output into a structured `QueryResponse`:

```json
{
    "issue_type": "delivery_underperformance",
    "entities": ["C0042"],
    "summary": "Detected delivery underperformance. Audit creative assets for fatigue and refresh if CTR has declined >20%. Confidence: 50% based on 3 evidence point(s).",
    "evidence": [
        "[DB] Campaign C0042 | \"Summer Sale\" | impressions=150000 | clicks=3200 | status=active",
        "[DB] Inventory inv_042 | publisher=PubMatic | viewability_rate=0.72 | floor_price=0.45",
        "[KB] Low viewability can cause impression loss"
    ],
    "root_cause": "Audit creative assets for fatigue and refresh if CTR has declined >20%. Based on data: Campaign C0042 | \"Summer Sale\" | impressions=150000 | clicks=3200 | status=active",
    "confidence": 0.5,
    "recommended_actions": [
        "Audit creative assets for fatigue and refresh if CTR has declined >20%.",
        "Verify pacing configuration aligns with flight dates.",
        "Check daily caps and frequency caps for over-restriction."
    ],
    "escalation": "low"
}
```

### 7.2 Escalation Levels

| Level | Threshold | Action |
|-------|-----------|--------|
| `critical` | Fraud/brand safety + confidence >= 0.8 | Immediate alert, pager duty |
| `high` | Fraud, brand safety, or budget depletion | Review within 1 hour |
| `medium` | Inventory shortage, budget depletion | Review within 4 hours |
| `low` | All other issues | Review during next business cycle |

### 7.3 Report Sections

Each investigation report includes:

1. **Summary** — One-sentence plain-language finding
2. **Root Cause** — Hypothesised primary cause
3. **Confidence** — Numerical score with interpretation
4. **Evidence** — Supporting data points with source tags
5. **Recommended Actions** — Prioritised remediation steps
6. **Escalation Level** — Urgency classification

---

## 8. Example Walkthrough

### Scenario: Fill Rate Drop

**User Query:** *"Why is the fill rate dropping for C0042 on inv_042?"*

#### Step 1: Classification

```
QueryAgent input:  "Why is the fill rate dropping for C0042 on inv_042?"
QueryAgent output:
  issue_type: "fill_rate"
  entities: [
    {type: "campaign_id", value: "0042", raw_text: "C0042"},
    {type: "inventory_id", value: "042", raw_text: "inv_042"}
  ]
  time_range: {start: "2026-06-07", end: "2026-06-14", relative: "default_7_days"}
```

#### Step 2: Retrieval

```
RetrievalAgent input:  issue_type="fill_rate", entities=[...], time_range={...}
RetrievalAgent actions:
  1. Embed query text → vector
  2. Qdrant search (top_k=10) → 3 relevant snippets
  3. PostgreSQL: fetch campaign C0042 → {impressions=120000, spend=$45k, ...}
  4. PostgreSQL: fetch inventory inv_042 → {publisher="PubMatic", floor_price=0.45, ...}
RetrievalAgent output:
  snippets: [...],
  campaign_context: [{campaign_id: "C0042", impressions: 120000, ...}],
  inventory_context: [{inventory_id: "inv_042", publisher: "PubMatic", ...}]
```

#### Step 3: Analysis

```
AnalysisAgent input:  issue_type="fill_rate", entities=[...], retrieval_context={...}
AnalysisAgent computations:
  1. _collect_evidence() → [
    "[KB] Fill rate is the ratio of served impressions to ad requests...",
    "[DB] Campaign C0042 | \"Summer Sale\" | impressions=120000 | clicks=2800 | status=active",
    "[DB] Inventory inv_042 | publisher=PubMatic | viewability_rate=0.72 | floor_price=0.45"
  ]
  2. _infer_root_cause("fill_rate", evidence) → "Review bid strategy and daily budget allocation..."
  3. _compute_confidence(...) → 0.55
AnalysisAgent output:
  root_cause: "...Based on data: Campaign C0042 | impressions=120000 | ...",
  confidence: 0.55,
  evidence: [...],
  recommended_actions: ["Review bid strategy...", "Confirm deal pacing...", "Consider dayparting..."]
```

#### Step 4: Synthesis

```
ResponseAgent input:  classified={...}, retrieval_context={...}, analysis={...}
ResponseAgent output:
  issue_type: "fill_rate"
  entities: ["C0042", "inv_042"]
  summary: "Detected fill rate issue. Review bid strategy... Confidence: 55% based on 3 evidence point(s)."
  root_cause: "Review bid strategy and daily budget allocation. Based on data: Campaign C0042..."
  confidence: 0.55
  recommended_actions: ["Review bid strategy...", "Confirm deal pacing...", "Consider dayparting..."]
  escalation: "low"
```

#### Final Report (user-facing)

```
Issue: fill_rate
Entities: C0042, inv_042
──────────────────────────────────────────────────
Summary: Detected fill rate issue.
Review bid strategy and daily budget allocation.
Based on data: Campaign C0042 | "Summer Sale" |
impressions=120000 | clicks=2800 | status=active

Confidence: 55% (medium)

Evidence:
  [KB] Fill rate is the ratio of served impressions to ad requests...
  [DB] Campaign C0042 | impressions=120000 | clicks=2800 | status=active
  [DB] Inventory inv_042 | viewability_rate=0.72 | floor_price=0.45

Recommended Actions:
  1. Review bid strategy and daily budget allocation.
  2. Confirm deal pacing settings with the publisher.
  3. Consider dayparting adjustments to smooth delivery.

Escalation: LOW
```

---

## 9. API Reference

### POST /api/v1/ask

```
Request:
{
    "text": "Why is the fill rate dropping for C0042?",
    "time_range": null
}

Response:
{
    "issue_type": "fill_rate",
    "entities": ["C0042"],
    "summary": "...",
    "evidence": ["..."],
    "root_cause": "...",
    "confidence": 0.55,
    "recommended_actions": ["..."],
    "escalation": "low"
}
```

### Error Handling

| HTTP Status | Condition |
|-------------|-----------|
| 200 | Successful investigation |
| 422 | Validation error (empty query, invalid text) |
| 500 | Pipeline failure (agent error, DB connection lost) |

---

*For implementation details, see `src/agents/query_agent.py`, `src/agents/retrieval_agent.py`, `src/agents/analysis_agent.py`, and `src/agents/response_agent.py`.*
