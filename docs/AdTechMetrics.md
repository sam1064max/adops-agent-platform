# AdTech Metrics Reference — AdOps Agent Platform

**Version:** 0.1.0 | **Status:** Active Development  
**Last Updated:** 2026-06-14

---

## Table of Contents

1. [Fill Rate](#1-fill-rate)
2. [Win Rate and Bid Rate](#2-win-rate-and-bid-rate)
3. [Pacing Ratio](#3-pacing-ratio)
4. [eCPM](#4-ecpm)
5. [Auction Pressure](#5-auction-pressure)
6. [CTR and Viewability](#6-ctr-and-viewability)
7. [Inventory Health Scores](#7-inventory-health-scores)
8. [Metrics in Investigations](#8-metrics-in-investigations)

---

## 1. Fill Rate

### 1.1 Definition

Fill rate measures the percentage of ad requests that result in a served impression. It reflects the supply side's ability to fulfill demand.

### 1.2 Formula

```
Fill Rate (%) = (Served Impressions / Total Ad Requests) × 100
```

### 1.3 Interpretation

| Range | Label | Meaning |
|-------|-------|---------|
| 90–100% | Excellent | Healthy supply-demand match |
| 70–89% | Good | Minor friction in fill |
| 50–69% | Fair | Moderate fill issues |
| 0–49% | Poor | Significant supply problem |

### 1.4 Implementation

Calculated by `FillRateAnalyzer.calculate_fill_rate()`:

```python
def calculate_fill_rate(impressions: float, ad_requests: float) -> float:
    if ad_requests <= 0:
        return 0.0
    return round((impressions / ad_requests) * 100, 4)
```

### 1.5 Usage in Investigations

Fill rate analysis is used to detect:
- **Inventory shortages**: Fill rate <50% with stable ad requests → supply constraint
- **Floor price issues**: Fill rate drop coinciding with floor price change → pricing friction
- **SSP integration failures**: Sudden 0% fill on specific publisher → technical outage

### 1.6 Trends and Anomaly Detection

The `FillRateAnalyzer.analyze_fill_rate()` method tracks:

| Metric | Description |
|--------|-------------|
| `current_rate` | Latest daily fill rate |
| `previous_rate` | Prior day fill rate |
| `change_pct` | Day-over-day percentage change |
| `trend` | improving / declining / stable (based on z-score) |
| `anomalies` | List of sudden drops exceeding 15% threshold |

#### Sudden Drop Detection

Uses day-over-day comparison with configurable threshold:

```python
drop_pct = (previous_rate - current_rate) / previous_rate
if drop_pct >= 0.15:  # 15% drop threshold
    flag as anomaly
```

#### Inventory Shortage Detection

Identifies inventory sources with persistently low fill rates:

```python
if avg_fill_rate < min_fill_rate:         # default 50%
    status = "warning"
if avg_fill_rate < min_fill_rate * 0.5:   # below 25%
    status = "critical"
```

#### Request Spike Detection

Uses z-score to identify unusual request volume:

```python
z_score = (value - mean) / std
if abs(z_score) >= 2.0:
    flag as spike
```

---

## 2. Win Rate and Bid Rate

### 2.1 Bid Rate

Bid rate measures how often an ad request receives at least one bid.

```
Bid Rate (%) = (Requests with Bids / Total Ad Requests) × 100
```

**Interpretation:** A low bid rate suggests the floor price exceeds buyer willingness, targeting is too narrow, or demand is insufficient.

### 2.2 Win Rate

Win rate measures the percentage of submitted bids that win the auction.

```
Win Rate (%) = (Won Auctions / Total Bids Submitted) × 100
```

**Interpretation:** A low win rate suggests the bid price is too low relative to competition, or the ad quality/relevance is subpar.

### 2.3 Combined Analysis

| Scenario | Bid Rate | Win Rate | Likely Cause |
|----------|----------|----------|-------------|
| Low fill | Low | Low | Floor price too high |
| Low fill | High | Low | Bid price too low |
| Low fill | High | High | Inventory shortage |
| Low fill | Low | High | Targeting too narrow |

### 2.4 Implementation

Win rate is computed from delivery logs:

```python
total_bids = sum(delivery_logs["impressions"]) + estimated_lost_bids
wins = sum(delivery_logs["impressions"])
win_rate = (wins / total_bids) * 100 if total_bids else 0.0
```

---

## 3. Pacing Ratio

### 3.1 Definition

Pacing ratio measures how evenly campaign delivery is spread across its flight duration. It answers: "Are we on track to spend the full budget by the end date?"

### 3.2 Formula

```
Expected Pct = (Days Elapsed / Total Days) × 100

Pace Pct = (Delivered / Total Target) × 100

Pace Ratio = Pace Pct / Expected Pct
```

### 3.3 Interpretation

| Pace Ratio | Status | Meaning |
|------------|--------|---------|
| < 0.8 | Underdelivering | Behind schedule — risk of unspent budget |
| 0.8–1.2 | On track | Delivering as expected |
| > 1.2 | Overdelivering | Ahead of schedule — risk of premature budget depletion |

### 3.4 Implementation

Calculated by `PacingAnalyzer.calculate_pacing()`:

```python
expected_pct = (days_elapsed / total_days) * 100
pace_pct = (delivered / target) * 100
daily_rate = delivered / days_elapsed
projected_total = delivered + (daily_rate * remaining_days)

if pace_pct < expected_pct * 0.8:
    status = "underdelivering"
elif pace_pct > expected_pct * 1.2:
    status = "overdelivering"
else:
    status = "on_track"
```

### 3.5 Budget Consumption

The `calculate_budget_consumption()` method tracks spend pacing:

```
Consumption Pct = (Spent / Budget) × 100
Daily Burn = Spent / Days Elapsed
Projected Total = Spent + (Daily Burn × Remaining Days)
Projected Overrun = Projected Total - Budget

Status: burning_fast (consumption > expected × 1.2)
        underspending (consumption < expected × 0.8)
        on_track
```

### 3.6 Under/Over Delivery Detection

| Method | Threshold | Flags |
|--------|-----------|-------|
| `detect_underdelivery()` | pace_ratio < 0.8 | Campaigns with delivery deficit |
| `detect_overdelivery()` | pace_ratio > 1.2 | Campaigns exceeding pace |

---

## 4. eCPM

### 4.1 Definition

Effective Cost Per Mille (eCPM) measures revenue earned per 1,000 impressions. It is the primary monetisation efficiency metric.

### 4.2 Formula

```
eCPM = (Total Revenue / Total Impressions) × 1,000
```

### 4.3 Variants

| Variant | Formula | Use Case |
|---------|---------|----------|
| eCPM (publisher) | (Revenue / Impressions) × 1000 | Publisher monetisation |
| eCPM (buyer) | (Spend / Impressions) × 1000 | Buyer cost efficiency |
| RPM | (Revenue / Page Views) × 1000 | Site-level monetisation |

### 4.4 Interpretation

| eCPM Range | Classification | Typical Context |
|------------|---------------|-----------------|
| < $0.50 | Low | Display, remnant inventory |
| $0.50–$2.00 | Moderate | Standard display, mobile web |
| $2.00–$5.00 | Good | Video, premium display |
| $5.00–$15.00 | High | Premium video, CTV |
| > $15.00 | Very High | Specialised verticals, private marketplace |

### 4.5 Usage in Investigations

eCPM drops are investigated alongside:
- Fill rate changes (more low-value impressions)
- Floor price changes (price too high/lower than market)
- Channel mix shifts (move to lower-eCPM inventory)

---

## 5. Auction Pressure

### 5.1 Definition

Auction pressure measures the competitiveness of the bid landscape. High auction pressure means many buyers competing for the same impression.

### 5.2 Indicators

| Metric | High Pressure | Low Pressure |
|--------|--------------|--------------|
| Bid count per auction | >10 bidders | <3 bidders |
| Win rate | <20% | >60% |
| CPM clearing price | Well above floor | Near floor price |
| Time to clear | <50ms | >200ms |

### 5.3 Impact

| Pressure Level | Buyer Impact | Seller Impact |
|---------------|--------------|---------------|
| High | Lower win rates, higher CPMs | Higher revenue per impression |
| Moderate | Stable delivery, fair CPMs | Predictable fill rates |
| Low | High win rates, low CPMs | Low revenue, high unfilled rate |

### 5.4 Detection

Auction pressure anomalies are detected via:
- Win rate drops with stable bids → increased competition
- Fill rate drops with stable requests → auction not clearing
- CPM increases with stable win rate → demand-side price increase

---

## 6. CTR and Viewability

### 6.1 Click-Through Rate (CTR)

**Formula:**
```
CTR (%) = (Clicks / Impressions) × 100
```

**Benchmarks (display, US market):**

| Format | Average CTR | Good CTR | Excellent CTR |
|--------|-------------|----------|---------------|
| Display banner | 0.05–0.10% | >0.15% | >0.30% |
| Native | 0.15–0.30% | >0.40% | >0.80% |
| Video pre-roll | 0.30–0.80% | >1.00% | >2.00% |
| Social feed | 0.50–1.00% | >1.50% | >3.00% |

**Detection methods in `CTRAnalyzer`:**
- `analyze_ctr()` — Trend analysis with 7-day and 30-day moving averages
- `detect_creative_fatigue()` — Compares recent window CTR to earlier window
- `detect_audience_mismatch()` — Identifies segments with CTR significantly below average

**Fatigue detection:**
```python
fatigue_ratio = (earlier_window_avg - recent_window_avg) / earlier_window_avg
if fatigue_ratio > 0.15:  # 15% decline
    flag as fatigued
```

### 6.2 Viewability

**Definition (IAB标准):** An ad is viewable if ≥50% of its pixels are on-screen for ≥1 second (display) or ≥2 seconds (video).

**Formula:**
```
Viewability Rate (%) = (Viewable Impressions / Measured Impressions) × 100
```

**Thresholds:**

| Rating | Viewability Rate | Action |
|--------|-----------------|--------|
| Excellent | ≥80% | No action needed |
| Good | 70–79% | Monitor |
| Poor | 50–69% | Investigate placement quality |
| Critical | <50% | Shift budget away |

**Usage:** `InventoryMetadata.viewability_rate` tracks per-inventory viewability. The `InventoryAnalyzer` incorporates viewability into the health score (40% weight).

---

## 7. Inventory Health Scores

### 7.1 Definition

A composite 0–100 score measuring the overall quality and reliability of an inventory source.

### 7.2 Formula (`InventoryAnalyzer.get_inventory_health_score()`)

```
Fill Rate Score:     min(fill_rate / 100 × 100, 100)                          40% weight
CTR Score:           min(ctr / 5 × 100, 100)                                   30% weight
Volume Score:        min(impressions / ad_requests × 100, 100)                 20% weight
Fulfillment Score:   min(impressions / max(ad_requests, 1) × 100, 100)        10% weight

Health Score = (Fill Rate Score × 0.40) +
               (CTR Score × 0.30) +
               (Volume Score × 0.20) +
               (Fulfillment Score × 0.10)
               (clamped to 0–100)
```

### 7.3 Interpretation

| Score Range | Label | Action |
|-------------|-------|--------|
| 80–100 | Healthy | Continue normal allocation |
| 60–79 | Fair | Monitor for degradation |
| 40–59 | At Risk | Investigate underlying issues |
| 0–39 | Critical | Reduce allocation, escalate |

### 7.4 Dashboard Health Score Calculation

In the dashboard router, a simplified health score is computed:

```python
score = min(
    40 * viewability_rate
    + 30 * brand_safety_score
    + 30 * min(available_impressions / 500000, 1),
    100
)
```

This version uses:
- Viewability rate (40%) — higher viewability = better quality
- Brand safety score (30%) — higher safety = lower risk
- Available impressions scaled to 500k cap (30%) — more supply = more reliable

---

## 8. Metrics in Investigations

### 8.1 Metric-to-Issue Mapping

| Metric Anomaly | Trigger Threshold | Investigated Issue Type |
|---------------|-------------------|----------------------|
| Fill rate drop | >15% day-over-day | `fill_rate`, `inventory_shortage` |
| Pacing deviation | pace_ratio < 0.8 or > 1.2 | `pacing_anomaly`, `budget_depletion` |
| CTR decline | >20% vs 7d moving average | `ctr`, `creative_fatigue` |
| Spend spike | >3σ from mean daily spend | `pacing_anomaly` |
| Fraud score | >0.5 | `fraud_signal` |
| Viewability drop | <50% | `viewability_drop` |
| Brand safety | score <0.8 | `brand_safety` |

### 8.2 Cross-Metric Correlation

Investigations often combine multiple metrics:

| Symptom Pattern | Likely Root Cause |
|----------------|-------------------|
| Fill rate ↓ + Ad requests → | Inventory shortage |
| Fill rate ↓ + Floor price ↑ | Price friction |
| CTR ↓ + Impressions → | Creative fatigue |
| CTR ↓ + Impressions ↓ | Audience targeting issue |
| Spend ↑ + CTR ↓ | Low-quality placement expansion |
| Spend ↑ + Conversions → | Budget inefficiency |

### 8.3 Metrics in the Dashboard

The internal dashboard shows real-time metric snapshots:

| Dashboard Page | Key Metrics Displayed |
|----------------|----------------------|
| Operational Summary | Active campaigns, total spend, fill rate, health % |
| Campaign Health | Budget, spend, pace ratio, CTR |
| Campaign Detail | CTR, CPA, ROAS, win rate, fill rate, pacing gauge |
| Inventory Health | Viewability, brand safety, floor price, health score |
| Risks | Budget depletion %, pacing deficit, fraud scores |
| Anomalies | Spend spikes, CTR drops, pacing deviations, fraud signals |

---

*Reference implementations: `src/analytics/fill_rate_analyzer.py`, `src/analytics/pacing_analyzer.py`, `src/analytics/ctr_analyzer.py`, `src/analytics/inventory_analyzer.py`.*
