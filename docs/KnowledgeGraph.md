# Knowledge Graph — AdOps Agent Platform

**Version:** 0.1.0 | **Status:** Planned  
**Last Updated:** 2026-06-14

---

## Table of Contents

1. [Overview](#1-overview)
2. [Entity Types and Relationships](#2-entity-types-and-relationships)
3. [Graph Schema](#3-graph-schema)
4. [Impact Tracing](#4-impact-tracing)
5. [Graph Queries](#5-graph-queries)
6. [Example Queries](#6-example-queries)
7. [Integration with Agent Pipeline](#7-integration-with-agent-pipeline)
8. [Future Plans](#8-future-plans)

---

## 1. Overview

The Knowledge Graph maps entities in the AdOps ecosystem — campaigns, inventory sources, creatives, publishers, geos, and devices — and the relationships between them. It enables multi-hop impact tracing, root cause path analysis, and holistic dependency mapping.

### 1.1 Purpose

- **Impact analysis**: "Which campaigns are affected if publisher X goes down?"
- **Root cause path tracing**: "What is the shortest path between this metric anomaly and its likely cause?"
- **Dependency mapping**: "Which inventory sources serve which campaigns?"
- **Anomaly scope assessment**: "How many entities are affected by this issue?"

### 1.2 Current Status

The knowledge graph is in the **planned** phase. Entity relationships are implicitly present in the relational database (foreign keys between `campaigns`, `delivery_logs`, `inventory_metadata`) and the vector store (`adops_knowledge` collection). A dedicated graph layer will be built on top of these existing data sources.

### 1.3 Planned Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Graph DB | NetworkX (in-memory) or Neo4j (persistent) | Graph storage and traversal |
| Entity extraction | QueryAgent (existing) + additional NLP | Extract entities from queries and documents |
| Relationship inference | Rule-based + ML | Infer edges from delivery data and knowledge base |
| Query layer | Custom path-finding algorithms | Impact tracing and root cause analysis |

---

## 2. Entity Types and Relationships

### 2.1 Entity Types

| Entity Type | Source Table | Key Attributes | Examples |
|-------------|-------------|----------------|----------|
| **Campaign** | `campaigns` | id, name, advertiser, budget, status, start_date, end_date | C0042, "Summer Sale" |
| **Inventory** | `inventory_metadata` | id, publisher, domain, ad_format, floor_price | inv_042, PubMatic |
| **Publisher** | `inventory_metadata.publisher` | name | PubMatic, OpenX, Magnite |
| **Domain** | `inventory_metadata.domain` | url | example.com, news-site.com |
| **Creative** | (planned) | id, format, dimensions, url | CR-001, 300x250-banner |
| **Advertiser** | `campaigns.advertiser` | name | Nike, Ford, P&G |
| **Delivery Log** | `delivery_logs` | id, campaign_id, timestamp, impressions, clicks, spend, geo, device | log_12345 |
| **Geo** | `delivery_logs.geo` | region code | US, UK, DE, FR |
| **Device** | `delivery_logs.device` | type | desktop, mobile, tablet, ctv |

### 2.2 Relationship Types

| Relationship | From | To | Cardinality | Description |
|-------------|------|----|-------------|-------------|
| `RUNS_ON` | Campaign | Inventory | M:N | Campaign delivers on inventory sources |
| `OWNS` | Publisher | Inventory | 1:N | Publisher owns inventory sources |
| `HOSTS` | Domain | Inventory | 1:N | Domain hosts ad units |
| `SERVED_BY` | DeliveryLog | Campaign | N:1 | Log entry belongs to campaign |
| `FROM_INVENTORY` | DeliveryLog | Inventory | N:1 | Log entry sourced from inventory |
| `BELONGS_TO` | Campaign | Advertiser | N:1 | Campaign managed by advertiser |
| `TARGETS` | Campaign | Geo | M:N | Campaign targets geographic regions |
| `DELIVERS_ON` | DeliveryLog | Device | N:1 | Delivery on specific device type |
| `USES` | Campaign | Creative | M:N | Campaign uses creatives |
| `RELATED_TO` | Entity | Entity | M:N | Generic similarity/correlation edge |

### 2.3 Entity Relationship Diagram

```
                    ┌──────────────┐
                    │  Advertiser  │
                    └──────┬───────┘
                           │ BELONGS_TO
                           │
                    ┌──────▼───────┐
                    │   Campaign   │◄─────────┐
                    └──────┬───────┘           │
                           │ RUNS_ON           │ USES
                           │                   │
                    ┌──────▼───────┐    ┌──────┴────────┐
                    │  Inventory   │    │   Creative    │
                    └──────┬───────┘    └───────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
      ┌───────▼────┐ ┌────▼─────┐ ┌────▼────────┐
      │  Publisher │ │  Domain  │ │  Ad Format  │
      └────────────┘ └──────────┘ └─────────────┘

    ┌─────────────────────────────────────────────┐
    │               DeliveryLog                    │
    │  campaign_id ──→ Campaign (SERVED_BY)        │
    │  publisher   ──→ Publisher (FROM_PUBLISHER)  │
    │  geo         ──→ Geo (TARGETS)               │
    │  device      ──→ Device (DELIVERS_ON)        │
    └─────────────────────────────────────────────┘
```

---

## 3. Graph Schema

### 3.1 Node Properties

**Campaign Node:**
```json
{
    "id": "C0042",
    "type": "campaign",
    "name": "Summer Sale",
    "advertiser": "Nike",
    "status": "active",
    "budget": 100000.0,
    "spend": 45000.0,
    "impressions": 2500000,
    "start_date": "2026-05-01",
    "end_date": "2026-06-30"
}
```

**Inventory Node:**
```json
{
    "id": "inv_042",
    "type": "inventory",
    "publisher": "PubMatic",
    "domain": "premium-news.com",
    "ad_format": "display",
    "floor_price": 0.45,
    "viewability_rate": 0.72,
    "brand_safety_score": 0.95,
    "available_impressions": 500000
}
```

**Publisher Node:**
```json
{
    "id": "pubmatic",
    "type": "publisher",
    "name": "PubMatic",
    "total_inventory": 15,
    "avg_viewability": 0.68,
    "avg_brand_safety": 0.92
}
```

### 3.2 Edge Properties

**RUNS_ON edge:**
```json
{
    "relationship": "RUNS_ON",
    "source": "campaign/C0042",
    "target": "inventory/inv_042",
    "properties": {
        "impressions_delivered": 450000,
        "spend": 12500.0,
        "fill_rate": 0.78,
        "avg_fraud_score": 0.05,
        "active_days": 30
    }
}
```

**DELIVERS_ON edge:**
```json
{
    "relationship": "DELIVERS_ON",
    "source": "delivery_log/12345",
    "target": "device/mobile",
    "properties": {
        "impressions": 15000,
        "clicks": 45,
        "ctr": 0.003
    }
}
```

---

## 4. Impact Tracing

### 4.1 Forward Impact

**Question:** "Which campaigns are affected if publisher PubMatic goes down?"

Traversal path:
```
Publisher:PubMatic ──OWNS──▶ Inventory:inv_042
Publisher:PubMatic ──OWNS──▶ Inventory:inv_089
Inventory:inv_042 ──RUNS_ON──▶ Campaign:C0042
Inventory:inv_042 ──RUNS_ON──▶ Campaign:C0088
Inventory:inv_089 ──RUNS_ON──▶ Campaign:C0042
```

**Result:** Campaigns C0042 and C0088 are impacted with combined delivery of 450k impressions via PubMatic inventory.

### 4.2 Backward Impact (Root Cause Path)

**Question:** "What is the root cause path for campaign C0042's fill rate drop?"

Traversal path:
```
Campaign:C0042 ──RUNS_ON──▶ Inventory:inv_042
Inventory:inv_042 ──OWNED_BY──▶ Publisher:PubMatic
                                    │
                                    ▼
                            (check publisher health)
                            ── has correlation edges to ──▶ SSP outage event
```

**Result:** Publisher PubMatic had a 3-hour SSP outage that prevented bid responses, causing a fill rate drop on inv_042 which affected C0042.

### 4.3 Scope Assessment

**Question:** "How many entities are affected by the creative rejection on CR-001?"

Traversal path:
```
Creative:CR-001 ──USES──▶ Campaign:C0042
Creative:CR-001 ──USES──▶ Campaign:C0123
Campaign:C0042 ──RUNS_ON──▶ Inventory:inv_042, inv_089, inv_101
Campaign:C0123 ──RUNS_ON──▶ Inventory:inv_055, inv_067
```

**Impact scope:** 2 campaigns, 5 inventory sources, 3 publishers.

---

## 5. Graph Queries

### 5.1 Entity Lookup

```
# Find all inventory for a publisher
MATCH (pub:Publisher {name: "PubMatic"})-[:OWNS]->(inv:Inventory)
RETURN inv.id, inv.domain, inv.floor_price

# Find all campaigns on an inventory source
MATCH (inv:Inventory {id: "inv_042"})<-[:RUNS_ON]-(camp:Campaign)
RETURN camp.id, camp.name, camp.status, camp.budget
```

### 5.2 Impact Analysis

```
# Forward impact: find all campaigns depending on a publisher
MATCH (pub:Publisher {name: "PubMatic"})-[:OWNS]->(inv:Inventory)<-[:RUNS_ON]-(camp:Campaign)
WHERE camp.status = "active"
RETURN camp.id, camp.name, sum(inv.available_impressions) as total_supply
ORDER BY total_supply DESC

# Backward impact: find the supply chain for a campaign
MATCH path = (camp:Campaign {id: "C0042"})-[:RUNS_ON]->(inv:Inventory)-[:OWNED_BY]->(pub:Publisher)
RETURN path
```

### 5.3 Anomaly Correlation

```
# Find shared inventory between two underperforming campaigns
MATCH (c1:Campaign {id: "C0042"})-[:RUNS_ON]->(inv:Inventory)<-[:RUNS_ON]-(c2:Campaign {id: "C0088"})
RETURN inv.id, inv.publisher, inv.domain

# Find campaigns with high fraud scores on the same inventory
MATCH (inv:Inventory)<-[:RUNS_ON]-(camp:Campaign)
MATCH (inv)<-[:FROM_INVENTORY]-(log:DeliveryLog)
WHERE log.fraud_score > 0.5
RETURN inv.id, count(DISTINCT camp) as affected_campaigns, count(log) as fraud_events
```

### 5.4 Path Finding

```
# Shortest path between a fraud signal and its source
MATCH path = shortestPath(
    (log:DeliveryLog {id: "log_12345"})-[*]-(src:Publisher)
)
WHERE log.fraud_score > 0.7
RETURN path

# All paths from a geo anomaly to affected campaigns
MATCH path = (geo:Geo {code: "XX"})-[*]-(camp:Campaign)
RETURN path, length(path) as hops
ORDER BY hops
```

---

## 6. Example Queries

### 6.1 Campaign Dependency Map

```cypher
// Which inventory sources power campaign C0042?
MATCH (camp:Campaign {id: "C0042"})-[:RUNS_ON]->(inv:Inventory)-[:OWNED_BY]->(pub:Publisher)
RETURN
    camp.name as Campaign,
    inv.id as Inventory,
    pub.name as Publisher,
    inv.floor_price as FloorPrice,
    inv.viewability_rate as Viewability
ORDER BY inv.floor_price DESC
```

**Expected result:**

| Campaign | Inventory | Publisher | Floor Price | Viewability |
|----------|-----------|-----------|-------------|-------------|
| Summer Sale | inv_042 | PubMatic | 0.45 | 72% |
| Summer Sale | inv_089 | OpenX | 0.35 | 65% |
| Summer Sale | inv_101 | Magnite | 0.50 | 80% |

### 6.2 Publisher Health Impact

```cypher
// What is the total campaign budget depending on each publisher?
MATCH (pub:Publisher)<-[:OWNED_BY]-(inv:Inventory)<-[:RUNS_ON]-(camp:Campaign)
WHERE camp.status = "active"
RETURN
    pub.name as Publisher,
    count(DISTINCT camp) as CampaignCount,
    count(DISTINCT inv) as InventoryCount,
    round(sum(camp.budget)) as TotalBudget,
    round(avg(camp.spend / camp.budget * 100), 1) as AvgPacePct
ORDER BY TotalBudget DESC
```

### 6.3 Anomaly Spread Analysis

```cypher
// Find all entities connected to a high-fraud inventory source
MATCH (inv:Inventory {id: "inv_042"})
OPTIONAL MATCH (inv)<-[:RUNS_ON]-(camp:Campaign)
OPTIONAL MATCH (inv)<-[:FROM_INVENTORY]-(log:DeliveryLog)
WHERE log.fraud_score > 0.3
RETURN
    inv.id as SourceInventory,
    count(DISTINCT camp) as AffectedCampaigns,
    count(DISTINCT log) as HighFraudEvents,
    collect(DISTINCT camp.id) as CampaignList
```

### 6.4 Cross-Entity Correlation

```cypher
// Campaigns that share the same geo targeting issue
MATCH (camp:Campaign)-[:TARGETS]->(geo:Geo)
WHERE geo.code IN ["XX", "YY"]
MATCH (camp)-[:RUNS_ON]->(inv:Inventory)
RETURN
    geo.code as Geo,
    count(DISTINCT camp) as Campaigns,
    count(DISTINCT inv) as InventorySources,
    round(avg(camp.ctr), 4) as AvgCTR,
    round(avg(camp.spend / camp.budget * 100), 1) as AvgPace
ORDER BY AvgCTR ASC
```

### 6.5 Impact Radius

```cypher
// 2-hop impact analysis from a publisher outage
MATCH (pub:Publisher {name: "PubMatic"})-[:OWNS]->(inv:Inventory)
WITH collect(inv) as inventories
MATCH (inv:Inventory)-[:RUNS_ON]->(camp:Campaign)
WHERE inv IN inventories AND camp.status = "active"
RETURN
    camp.advertiser as Advertiser,
    count(DISTINCT camp) as Campaigns,
    round(sum(camp.budget)) as ExposedBudget
ORDER BY ExposedBudget DESC
```

---

## 7. Integration with Agent Pipeline

### 7.1 Current Integration Points

The knowledge graph currently relies on implicit relationships in the relational database:

```
QueryAgent           ── extracts entity IDs from queries
RetrievalAgent       ── fetches entity context from PostgreSQL
AnalysisAgent        ── uses entity relationships in evidence formatting
```

### 7.2 Planned Enhancement

```
QueryAgent           ── extracts entities + relationship hints
RetrievalAgent       ── vector search + graph traversal (2-hop neighbor fetch)
Knowledge Graph     ── explicit graph DB for relationship queries
AnalysisAgent        ── incorporates graph path features into confidence scoring
ResponseAgent        ── includes impact scope and dependency path in report
```

### 7.3 Graph-Enhanced Investigation Flow

```
User: "Why is C0042 underperforming?"

1. QueryAgent extracts: campaign=C0042, issue=underdelivery

2. RetrievalAgent:
   a. Vector search → KB snippets about underdelivery
   b. PostgreSQL → campaign C0042 details
   c. Graph query → "Which inventory sources does C0042 use?"
      ── returns [inv_042 (PubMatic, fill_rate:78%),
                   inv_089 (OpenX, fill_rate:92%)]

3. AnalysisAgent:
   a. Notices inv_042 fill_rate (78%) is significantly lower than inv_089 (92%)
   b. Graph query → "What other campaigns use inv_042?"
      ── returns [C0088, C0123]
   c. Cross-reference → C0088 also reporting fill rate drop
   d. Conclusion: Issue is likely inventory-specific, not campaign-specific

4. ResponseAgent:
   "Campaign C0042 is underperforming due to fill rate issues on inv_042
    (PubMatic, 78%). This inventory also serves campaigns C0088 and C0123,
    suggesting a supply-side problem rather than a campaign configuration issue."
```

---

## 8. Future Plans

### 8.1 Phase 1 — In-Memory Graph (NetworkX)

- Build graph from PostgreSQL data at startup
- Support for path finding and impact queries
- Expose via simple Python API in `src/knowledge_graph/`

### 8.2 Phase 2 — Persistent Graph DB (Neo4j)

- Dedicated Neo4j instance for production use
- Cypher query support
- Real-time graph updates from ingestion pipeline
- Graph-based alert correlation

### 8.3 Phase 3 — ML-Enhanced Relationship Inference

- Learn relationship weights from historical investigation outcomes
- Predict impact propagation paths
- Suggest root cause candidates based on graph topology

### 8.4 API Endpoints (Planned)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/kg/entity/{type}/{id}` | Get entity and its direct relationships |
| GET | `/kg/impact/{entity_type}/{entity_id}` | Forward impact analysis |
| GET | `/kg/path?from={}&to={}` | Shortest path between two entities |
| GET | `/kg/scope?entity_type={}&entity_id={}` | Impact radius assessment |
| POST | `/kg/query` | Raw graph query (Cypher or custom DSL) |

---

*This document describes planned functionality. For current entity relationship handling, see `src/agents/retrieval_agent.py` and `src/models/database.py`.*
