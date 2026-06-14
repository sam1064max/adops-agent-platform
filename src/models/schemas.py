"""Pydantic request / response schemas for the AdOps Agent Platform."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────

class IssueType(str, Enum):
    DELIVERY_UNDERPERFORMANCE = "delivery_underperformance"
    PACING_ANOMALY = "pacing_anomaly"
    FRAUD_SIGNAL = "fraud_signal"
    INVENTORY_SHORTAGE = "inventory_shortage"
    CREATIVE_FATIGUE = "creative_fatigue"
    BUDGET_DEPLETION = "budget_depletion"
    GEO_MISMATCH = "geo_mismatch"
    VIEWABILITY_DROP = "viewability_drop"
    BRAND_SAFETY = "brand_safety"
    GENERAL = "general"


class EscalationLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ── Query Agent Models ─────────────────────────────────────────────────────

class Entity(BaseModel):
    """An extracted entity from a natural-language query."""
    type: str
    value: str
    raw_text: str = ""


class TimeRange(BaseModel):
    """A resolved time range from a natural-language query."""
    start: str
    end: str
    relative: str = "unknown"


class QueryClassification(BaseModel):
    """Output of QueryAgent.classify_issue()."""
    issue_type: str
    entities: List[Entity] = Field(default_factory=list)
    time_range: TimeRange


# ── Request Models ───────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096, description="Natural-language query")
    time_range: Optional[TimeRange] = Field(default=None, description="Optional time window filter")


class IngestRequest(BaseModel):
    data_type: str = Field(..., description="Type of data being ingested")
    payload: List[Dict] = Field(..., min_items=1, description="Rows of data to ingest")
    source: Optional[str] = Field(default=None, description="Origin system identifier")


# ── Response Models ──────────────────────────────────────────────────────────

class QueryResponse(BaseModel):
    issue_type: IssueType
    entities: List[str] = Field(default_factory=list, description="Relevant entity IDs")
    summary: str = Field(..., description="Plain-language summary of the finding")
    evidence: List[str] = Field(default_factory=list, description="Supporting data points")
    root_cause: Optional[str] = Field(default=None, description="Hypothesised root cause")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score")
    recommended_actions: List[str] = Field(default_factory=list)
    escalation: EscalationLevel


class IngestResponse(BaseModel):
    rows_ingested: int
    message: str


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    postgres: str = "unknown"
    qdrant: str = "unknown"


# ── Analytics / Domain Models ────────────────────────────────────────────────

class CampaignMetrics(BaseModel):
    campaign_id: str
    impressions: int = 0
    clicks: int = 0
    conversions: int = 0
    spend: float = 0.0
    ctr: float = Field(default=0.0, description="Click-through rate")
    cpa: float = Field(default=0.0, description="Cost per acquisition")
    roas: float = Field(default=0.0, description="Return on ad spend")
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class InventoryItem(BaseModel):
    inventory_id: str
    publisher: str
    domain: Optional[str] = None
    format: str = Field(default="display", description="Ad format")
    floor_price: float = 0.0
    viewability_rate: float = 0.0
    brand_safety_score: float = 0.0
    available_impressions: int = 0


class DeliveryLog(BaseModel):
    log_id: Optional[str] = None
    campaign_id: str
    timestamp: datetime
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    publisher: Optional[str] = None
    domain: Optional[str] = None
    geo: Optional[str] = None
    device: Optional[str] = None
    fraud_score: float = 0.0
