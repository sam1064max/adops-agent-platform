# Root Cause Engine — AdOps Agent Platform

**Version:** 0.1.0 | **Status:** Active Development  
**Last Updated:** 2026-06-14

---

## Table of Contents

1. [Overview](#1-overview)
2. [How Root Causes Are Determined](#2-how-root-causes-are-determined)
3. [Confidence Scoring](#3-confidence-scoring)
4. [Evidence Weighting](#4-evidence-weighting)
5. [Root Cause Taxonomy](#5-root-cause-taxonomy)
6. [Issue Type Analysis](#6-issue-type-analysis)
7. [Examples](#7-examples)

---

## 1. Overview

The Root Cause Engine is the analytical core of the AdOps Agent Platform. It takes a classified issue type and a set of retrieved evidence, then produces a hypothesised root cause, a confidence score, and a list of recommended remediation actions.

The engine lives in `AnalysisAgent` (`src/agents/analysis_agent.py`) and operates as stage 3 of the investigation pipeline.

### Design Goals

- **Deterministic fallback**: Operates without an LLM for reliability and auditability
- **Evidence-grounded**: Every root cause is traceable to specific data points
- **Confidence-calibrated**: Scores reflect evidence richness and specificity
- **Extensible**: New issue types and evidence patterns can be added without changing pipeline structure

---

## 2. How Root Causes Are Determined

### 2.1 Process Flow

```
issue_type + entities[] + retrieval_context
                    │
                    ▼
          ┌─────────────────┐
          │ Collect Evidence │  ← snippets, campaign_context, inventory_context
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ Infer Root Cause │  ← map issue_type → hypothesis, ground with first DB evidence
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ Compute Score   │  ← evidence count, issue specificity, campaign data availability
          └────────┬────────┘
                   │
                   ▼
          ┌─────────────────┐
          │ Map Actions     │  ← action lookup by issue type
          └────────┬────────┘
                   │
                   ▼
     root_cause + confidence + evidence + actions
```

### 2.2 Evidence Collection

The engine collects evidence from three sources within the retrieval context:

| Source | Data Structure | Collection Strategy |
|--------|---------------|-------------------|
| **Snippets** (`[KB]`) | List of dicts with content, score, source_file | Top 5 by score, truncated to 300 chars |
| **Campaign context** (`[DB]`) | List of dicts with campaign_id, name, impressions, clicks, spend, status | All available, formatted as pipe-separated key=value |
| **Inventory context** (`[DB]`) | List of dicts with inventory_id, publisher, viewability_rate, floor_price | All available, formatted as pipe-separated key=value |

Evidence formatting produces human-readable strings:

```
[KB] Fill rate is the ratio of served impressions to total ad requests...
[DB] Campaign C0042 | "Summer Sale" | impressions=150000 | clicks=3200 | status=active
[DB] Inventory inv_042 | publisher=PubMatic | viewability_rate=0.72 | floor_price=0.45
```

### 2.3 Root Cause Inference

The `_infer_root_cause()` method uses a two-step approach:

**Step 1: Base hypothesis** — Look up the primary action from `_ACTION_MAP` by issue type:

```python
_ACTION_MAP = {
    "delivery_underperformance": [
        "Audit creative assets for fatigue and refresh if CTR has declined >20%.",
        "Verify pacing configuration aligns with flight dates.",
        ...
    ],
    "pacing_anomaly": [
        "Review bid strategy and daily budget allocation.",
        ...
    ],
    ...
}
```

**Step 2: Evidence grounding** — Find the first `[DB]`-tagged evidence item and append it:

```
"Audit creative assets for fatigue... Based on data: Campaign C0042 | impressions=150000 | ..."
```

This ensures the root cause is always traceable back to a specific data point.

---

## 3. Confidence Scoring

### 3.1 Score Computation

Confidence is computed by the `_compute_confidence()` method:

```python
def _compute_confidence(issue_type, evidence, campaigns):
    score = 0.3                          # Base
    if issue_type != "general":          # Specific issue bonus
        score += 0.2
    score += min(len(evidence) * 0.05, 0.3)   # Evidence volume
    score += min(len(campaigns) * 0.1, 0.2)    # Campaign data
    return min(score, 1.0)
```

### 3.2 Score Breakdown

| Component | Range | Contribution |
|-----------|-------|-------------|
| **Base** | 0.30 | Every investigation starts at 0.30 |
| **Issue specificity** | +0.20 if non-general | General issues are ambiguous |
| **Evidence volume** | +0.05 per item (max +0.30) | 6+ evidence items = full bonus |
| **Campaign data** | +0.10 per campaign (max +0.20) | 2+ campaigns = full bonus |

### 3.3 Score Interpretation

| Score Range | Label | Meaning |
|-------------|-------|---------|
| 0.00 – 0.35 | Minimal | Insufficient data for reliable root cause |
| 0.36 – 0.50 | Low | Some evidence found, but gaps exist |
| 0.51 – 0.70 | Medium | Multiple evidence sources support the hypothesis |
| 0.71 – 0.85 | High | Strong evidence alignment across sources |
| 0.86 – 1.00 | Very High | Definitive signal with corroborating context |

### 3.4 Confidence and Escalation

Confidence influences escalation level in the ResponseAgent:

- High-confidence (>=0.8) fraud or brand safety issues → **CRITICAL**
- Medium-confidence critical signals → **HIGH**
- Low-confidence signals → **LOW** (manual review advised)

---

## 4. Evidence Weighting

### 4.1 Current Weighting (Deterministic)

All evidence is treated equally in the current implementation. The number of evidence items affects confidence, but each item carries the same weight.

### 4.2 Planned Weighting Schema

The next iteration will introduce weighted evidence scoring:

| Evidence Type | Weight | Example | Rationale |
|--------------|--------|---------|-----------|
| **Direct metric** | 0.30 | "fill_rate dropped 40% in 24 hours" | Direct measurement of the issue |
| **Temporal** | 0.25 | "drop coincided with creative rotation at 00:00 UTC" | Causality signal |
| **Entity relationship** | 0.20 | "inventory C served 80% of campaign A's impressions" | Dependency evidence |
| **Historical baseline** | 0.15 | "fill rate is 2.1σ below 30-day moving average" | Deviation from norm |
| **External context** | 0.10 | "publisher reported SSP maintenance window" | Situational factor |

### 4.3 Evidence Quality Factors

Each evidence item will also be scored on quality:

| Quality Factor | Impact | Description |
|---------------|--------|-------------|
| Recency | ±15% | Evidence from last 24h weighted higher |
| Source reliability | ±20% | Direct DB records > knowledge base snippets |
| Specificity | ±15% | Numerical thresholds ("40% drop") > qualitative ("seems low") |
| Independence | ±10% | Correlated evidence de-weighted to avoid double-counting |

---

## 5. Root Cause Taxonomy

### 5.1 Issue Type Hierarchy

```
Delivery Issues
├── delivery_underperformance
│   ├── creative_fatigue
│   ├── pacing_anomaly
│   └── budget_depletion
├── fill_rate
│   ├── inventory_shortage
│   └── geo_mismatch
└── fraud_signal

Performance Issues
├── ctr
│   ├── creative_fatigue
│   └── audience_mismatch
└── viewability_drop

Supply Issues
├── inventory_shortage
└── brand_safety
```

### 5.2 Root Cause Patterns

| Issue Type | Primary Root Cause Pattern | Confidence Indicators |
|------------|---------------------------|---------------------|
| `delivery_underperformance` | CTR decline >20% + impression drop → creative fatigue | CTR trend, impression volume change |
| `pacing_anomaly` | Spend rate deviation >25% from expected → budget/bid issue | Daily spend variance, bidder timeout rate |
| `fraud_signal` | Fraud_score >0.5 + high request volume → invalid traffic | Fraud score distribution, GEO anomaly |
| `inventory_shortage` | Fill rate <50% + stable ad_requests → supply constraint | Fill rate trend, request-to-impression ratio |
| `budget_depletion` | Spend >85% of budget with >50% time remaining → over-pacing | Budget consumption rate, projected overrun |
| `viewability_drop` | Viewability <50% + impression growth → low-quality placements | Viewability by placement, domain breakdown |
| `geo_mismatch` | CTR variance >2σ across regions → targeting misconfiguration | Regional CTR distribution, impression share by GEO |

---

## 6. Issue Type Analysis

### 6.1 Delivery Underperformance

**Indicators:**
- Impressions declining over 3+ consecutive days
- CTR trending down >20% versus 7-day moving average
- Spend rate below target despite available budget

**Potential Root Causes (ranked):**
1. Creative fatigue (CTR-driven)
2. Pacing misconfiguration (budget capping)
3. Audience targeting drift
4. Publisher inventory loss
5. Competitive pressure (new campaigns entering auction)

### 6.2 Pacing Anomaly

**Indicators:**
- Pace ratio <0.8 (underdelivering) or >1.2 (overdelivering)
- Budget consumption rate mismatched to flight schedule
- Daily spend variance >±30% from expected daily budget

**Potential Root Causes:**
1. Bid strategy misconfiguration (under/over bidding)
2. Daily budget cap set too low/high
3. Frequency caps restricting delivery
4. Deal priority misalignment

### 6.3 Fill Rate Issue

**Indicators:**
- Fill rate <60% and dropping
- Ad request volume stable but impressions declining
- Floor price above market clearing rate

**Potential Root Causes:**
1. Inventory shortage from specific publishers
2. Floor price too high for demand
3. Creative rejection (size, format, certification)
4. SSP connection degradation

### 6.4 Fraud Signal

**Indicators:**
- Fraud_score >0.5 on delivery logs
- High impression volume from low-CTR sources
- Geographic mismatch (traffic from unexpected regions)
- Bot-like click patterns (even distribution, no conversion)

**Potential Root Causes:**
1. Invalid traffic from specific publishers/domains
2. Click fraud targeting high-value campaigns
3. Domain spoofing in programmatic deals

### 6.5 Inventory Shortage

**Indicators:**
- Available impressions declining for priority inventory
- Fill rate dropping on specific publisher domains
- Campaign failing to hit impression goal despite budget

**Potential Root Causes:**
1. Publisher yield optimization redirecting supply
2. Deal expiration or priority change
3. Seasonal supply contraction
4. Technical integration failure (SSP timeout)

---

## 7. Examples

### Example 1: Fill Rate Drop on Premium Inventory

**Context:**
```
Campaign: C0042 "Summer Sale" — budget $100k, impressions target 5M
Inventory: inv_042 — PubMatic, floor_price $0.45, viewability 72%
Issue: Fill rate dropped from 82% to 43% in 48 hours
```

**Evidence Collected:**
```
[DB] Campaign C0042 | "Summer Sale" | impressions=120000 | clicks=2800 | status=active
[DB] Inventory inv_042 | publisher=PubMatic | viewability_rate=0.72 | floor_price=0.45
[KB] Fill rate below 50% typically indicates supply constraint...
[KB] Floor prices above $0.40 may reduce bid density on open exchange
```

**Root Cause Determination:**
```
Primary pattern: fill_rate → inventory_shortage
Hypothesis: "Floor price $0.45 exceeds market clearing rate"
Evidence ground: Inventory inv_042 | floor_price=0.45
Confidence: 0.55 (medium — 4 evidence items, specific issue type)
```

**Recommendations:**
1. Review bid strategy and daily budget allocation
2. Confirm deal pacing settings with PubMatic
3. Consider dayparting adjustments to smooth delivery

### Example 2: CTR Decline and Creative Fatigue

**Context:**
```
Campaign: C0088 "Auto Leads Q2" — CTR dropped from 0.35% to 0.18% over 14 days
No creative rotation in 21 days
Impression volume stable at ~200k/day
```

**Evidence Collected:**
```
[DB] Campaign C0088 | "Auto Leads Q2" | impressions=2.8M | clicks=5040 | status=active
[DB] Campaign CTR trend: 0.35% → 0.28% → 0.22% → 0.18%
[KB] CTR decline >40% over 14+ days is strong indicator of creative fatigue
[KB] Industry benchmark: refresh creatives every 7-14 days for display campaigns
```

**Root Cause Determination:**
```
Primary pattern: ctr → creative_fatigue
Hypothesis: "Creative fatigue — CTR declined 49% over 14 days"
Evidence ground: Campaign C0088 | impressions=2.8M | clicks=5040
Confidence: 0.65 (medium-high — specific issue, temporal evidence, industry KB)
```

**Recommendations:**
1. Rotate in fresh creative assets
2. A/B test new headlines or CTAs
3. Reduce frequency cap temporarily while creatives refresh

### Example 3: Fraud Signal on High-Spend Campaign

**Context:**
```
Campaign: C0155 "Brand Awareness" — $500k budget
Delivery logs show fraud_score=0.82 on domain "suspicious-traffic.example.com"
CTR on that domain: 0.01% vs campaign average 0.28%
Conversions: 0 from 500k impressions
```

**Evidence Collected:**
```
[DB] Campaign C0155 | "Brand Awareness" | spend=$312k | impressions=8.1M | conversions=142
[DB] Delivery log | publisher="suspicious-traffic.example.com" | fraud_score=0.82 | geo=Unknown
[DB] Delivery log | click=42 | impressions=500k | CTR=0.01%
[KB] Fraud scores above 0.7 combined with anomalous CTR and zero conversions indicate IVT
```

**Root Cause Determination:**
```
Primary pattern: fraud_signal → IVT
Hypothesis: "Invalid traffic detected on suspicious-traffic.example.com"
Evidence ground: Delivery log | fraud_score=0.82 | publisher=suspicious-traffic.example.com
Confidence: 0.80 (high — direct fraud signal, corroborating CTR + conversion data)
```

**Recommendations:**
1. Flag high fraud-score line items for manual review
2. Enable pre-bid fraud filtering at the DSP level
3. Request publisher-side supply path transparency

---

*For implementation details, see `src/agents/analysis_agent.py`. The confidence scoring and action mapping are defined in `_compute_confidence()` and `_ACTION_MAP` respectively.*
