"""Investigation planner - classifies issues and generates structured investigation plans."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


# ── Shared data models ────────────────────────────────────────────────────────

class Entity(BaseModel):
    """An extracted domain entity from a natural-language query."""
    type: str
    value: str
    raw_text: str = ""


class TimeRange(BaseModel):
    """A resolved time window for the investigation."""
    start: str
    end: str
    relative: str = "unknown"


class InvestigationStep(BaseModel):
    """A single investigation task within a plan."""
    step_id: str
    description: str
    data_required: List[str] = Field(default_factory=list)
    analyzer: str = ""


class InvestigationPlan(BaseModel):
    """Structured plan produced by the InvestigationPlanner."""
    issue_type: str
    entities: List[Entity] = Field(default_factory=list)
    time_range: TimeRange
    steps: List[InvestigationStep] = Field(default_factory=list)
    raw_question: str = ""


# ── Issue-type classification ─────────────────────────────────────────────────

ISSUE_TYPES: List[str] = [
    "underdelivery",
    "ctr_drop",
    "fill_rate_drop",
    "inventory_failure",
    "revenue_decline",
    "pacing_issue",
    "forecast_risk",
    "bid_competitiveness",
    "budget_exhaustion",
]

_KEYWORD_MAP: Dict[str, List[str]] = {
    "underdelivery": [
        "underdeliver", "under delivery", "under-deliver",
        "not delivering", "delivery issue", "low delivery",
        "not serving", "serving issue", "slow delivery",
        "delivery drop", "delivery problem",
    ],
    "ctr_drop": [
        "ctr drop", "ctr decline", "ctr falling", "ctr decrease",
        "click-through drop", "low clicks", "clicks dropping",
        "click through rate down", "ctr down", "ctr low",
    ],
    "fill_rate_drop": [
        "fill rate drop", "fill rate low", "fill_rate decline",
        "low fill", "not filling", "unfilled", "no fill",
        "fill rate problem", "fill rate decrease", "fill not filling",
    ],
    "inventory_failure": [
        "inventory failure", "inventory issue", "inventory problem",
        "no inventory", "supply issue", "inventory shortage",
        "inventory not serving", "inventory drop", "inventory loss",
    ],
    "revenue_decline": [
        "revenue drop", "revenue decline", "revenue fell",
        "low revenue", "rpm drop", "earnings down",
        "revenue decrease", "money down", "income drop",
    ],
    "pacing_issue": [
        "pacing issue", "pacing behind", "pacing ahead",
        "over pace", "under pace", "pacing problem",
        "pacing off", "pacing wrong", "pace mismatch",
    ],
    "forecast_risk": [
        "forecast", "projection", "predict", "will it deliver",
        "can we hit", "will we reach", "forecast risk",
        "delivery forecast", "projected delivery",
    ],
    "bid_competitiveness": [
        "bid", "win rate", "bid price", "cpm",
        "auction", "competitiveness", "not winning",
        "losing bids", "bid strategy", "floor price",
    ],
    "budget_exhaustion": [
        "budget exhausted", "budget depletion", "running out",
        "spend too fast", "budget overspend", "budget overrun",
        "budget issue", "budget cap hit", "daily budget",
    ],
}

_STEP_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "underdelivery": [
        {"step_id": "s01", "description": "Check campaign pacing and delivery rate against expected trajectory", "data_required": ["campaign_metrics", "delivery_logs"], "analyzer": "pacing_analyzer"},
        {"step_id": "s02", "description": "Check inventory fill rate across active placements", "data_required": ["delivery_logs", "inventory_metadata"], "analyzer": "fill_rate_analyzer"},
        {"step_id": "s03", "description": "Check targeting configuration for over-restriction", "data_required": ["campaign_metrics"], "analyzer": "targeting_auditor"},
        {"step_id": "s04", "description": "Check bid competitiveness and win rate", "data_required": ["delivery_logs"], "analyzer": "bid_analyzer"},
        {"step_id": "s05", "description": "Check frequency caps and daily impression limits", "data_required": ["campaign_metrics", "delivery_logs"], "analyzer": "frequency_analyzer"},
        {"step_id": "s06", "description": "Analyze historical delivery trend for anomaly detection", "data_required": ["delivery_logs"], "analyzer": "trend_analyzer"},
    ],
    "ctr_drop": [
        {"step_id": "s01", "description": "Analyze CTR trend with moving averages", "data_required": ["delivery_logs"], "analyzer": "ctr_analyzer"},
        {"step_id": "s02", "description": "Detect creative fatigue via rolling window comparison", "data_required": ["delivery_logs"], "analyzer": "ctr_analyzer"},
        {"step_id": "s03", "description": "Check audience segment mismatch and deviation", "data_required": ["delivery_logs"], "analyzer": "ctr_analyzer"},
        {"step_id": "s04", "description": "Assess inventory quality scores by placement", "data_required": ["delivery_logs", "inventory_metadata"], "analyzer": "ctr_analyzer"},
        {"step_id": "s05", "description": "Check device and geo breakdown for CTR variance", "data_required": ["delivery_logs"], "analyzer": "segment_analyzer"},
        {"step_id": "s06", "description": "Compare current vs historical CTR benchmarks", "data_required": ["delivery_logs"], "analyzer": "trend_analyzer"},
    ],
    "fill_rate_drop": [
        {"step_id": "s01", "description": "Analyze fill rate trend and day-over-day change", "data_required": ["delivery_logs"], "analyzer": "fill_rate_analyzer"},
        {"step_id": "s02", "description": "Detect sudden fill rate drops beyond threshold", "data_required": ["delivery_logs"], "analyzer": "fill_rate_analyzer"},
        {"step_id": "s03", "description": "Check inventory availability and supply volume", "data_required": ["delivery_logs", "inventory_metadata"], "analyzer": "inventory_analyzer"},
        {"step_id": "s04", "description": "Check ad request volume anomalies", "data_required": ["delivery_logs"], "analyzer": "fill_rate_analyzer"},
        {"step_id": "s05", "description": "Analyze fill rate by region and publisher", "data_required": ["delivery_logs", "inventory_metadata"], "analyzer": "inventory_analyzer"},
        {"step_id": "s06", "description": "Check time-of-day fill rate patterns", "data_required": ["delivery_logs"], "analyzer": "trend_analyzer"},
    ],
    "inventory_failure": [
        {"step_id": "s01", "description": "Compute overall inventory health scores", "data_required": ["inventory_metadata", "delivery_logs"], "analyzer": "inventory_analyzer"},
        {"step_id": "s02", "description": "Detect inactive inventory sources with zero impressions", "data_required": ["inventory_metadata", "delivery_logs"], "analyzer": "inventory_analyzer"},
        {"step_id": "s03", "description": "Detect supply drops in daily impressions per placement", "data_required": ["delivery_logs"], "analyzer": "inventory_analyzer"},
        {"step_id": "s04", "description": "Analyze regional delivery breakdown for issues", "data_required": ["delivery_logs", "inventory_metadata"], "analyzer": "inventory_analyzer"},
        {"step_id": "s05", "description": "Check fill rates and price floors per placement", "data_required": ["delivery_logs", "inventory_metadata"], "analyzer": "fill_rate_analyzer"},
    ],
    "revenue_decline": [
        {"step_id": "s01", "description": "Analyze revenue and CPM trend over time", "data_required": ["delivery_logs", "campaign_metrics"], "analyzer": "revenue_analyzer"},
        {"step_id": "s02", "description": "Check fill rate impact on revenue", "data_required": ["delivery_logs"], "analyzer": "fill_rate_analyzer"},
        {"step_id": "s03", "description": "Check delivery volume impact on revenue", "data_required": ["delivery_logs"], "analyzer": "trend_analyzer"},
        {"step_id": "s04", "description": "Check rate card and floor price compliance", "data_required": ["inventory_metadata"], "analyzer": "bid_analyzer"},
        {"step_id": "s05", "description": "Analyze auction dynamics and bid density", "data_required": ["delivery_logs"], "analyzer": "bid_analyzer"},
    ],
    "pacing_issue": [
        {"step_id": "s01", "description": "Calculate pacing percentage and expected trajectory", "data_required": ["campaign_metrics", "delivery_logs"], "analyzer": "pacing_analyzer"},
        {"step_id": "s02", "description": "Check budget consumption and burn rate", "data_required": ["campaign_metrics", "delivery_logs"], "analyzer": "pacing_analyzer"},
        {"step_id": "s03", "description": "Analyze daily delivery pattern for weekend/weekday variation", "data_required": ["delivery_logs"], "analyzer": "trend_analyzer"},
        {"step_id": "s04", "description": "Check projected completion date and delivery forecast", "data_required": ["campaign_metrics", "delivery_logs"], "analyzer": "pacing_analyzer"},
        {"step_id": "s05", "description": "Check frequency capping impact on delivery rate", "data_required": ["campaign_metrics", "delivery_logs"], "analyzer": "frequency_analyzer"},
    ],
    "forecast_risk": [
        {"step_id": "s01", "description": "Analyze historical delivery performance and trends", "data_required": ["delivery_logs"], "analyzer": "trend_analyzer"},
        {"step_id": "s02", "description": "Check current pacing trajectory against target", "data_required": ["campaign_metrics", "delivery_logs"], "analyzer": "pacing_analyzer"},
        {"step_id": "s03", "description": "Analyze seasonal patterns and historical benchmarks", "data_required": ["delivery_logs"], "analyzer": "trend_analyzer"},
        {"step_id": "s04", "description": "Check inventory pipeline and supply availability", "data_required": ["inventory_metadata", "delivery_logs"], "analyzer": "inventory_analyzer"},
        {"step_id": "s05", "description": "Check budget runway and projected spend", "data_required": ["campaign_metrics", "delivery_logs"], "analyzer": "pacing_analyzer"},
    ],
    "bid_competitiveness": [
        {"step_id": "s01", "description": "Analyze win rate trend and current performance", "data_required": ["delivery_logs"], "analyzer": "bid_analyzer"},
        {"step_id": "s02", "description": "Check CPM distribution and bid price percentiles", "data_required": ["delivery_logs"], "analyzer": "bid_analyzer"},
        {"step_id": "s03", "description": "Compare bid price against floor price", "data_required": ["delivery_logs", "inventory_metadata"], "analyzer": "bid_analyzer"},
        {"step_id": "s04", "description": "Analyze auction density and competitor landscape", "data_required": ["delivery_logs"], "analyzer": "bid_analyzer"},
        {"step_id": "s05", "description": "Check bid request volume and eligibility rate", "data_required": ["delivery_logs"], "analyzer": "fill_rate_analyzer"},
    ],
    "budget_exhaustion": [
        {"step_id": "s01", "description": "Calculate budget consumption percentage and burn rate", "data_required": ["campaign_metrics", "delivery_logs"], "analyzer": "pacing_analyzer"},
        {"step_id": "s02", "description": "Check daily spend pace and projected overrun", "data_required": ["campaign_metrics", "delivery_logs"], "analyzer": "pacing_analyzer"},
        {"step_id": "s03", "description": "Analyze pacing pattern for spend acceleration", "data_required": ["delivery_logs"], "analyzer": "trend_analyzer"},
        {"step_id": "s04", "description": "Check remaining budget and days until exhaustion", "data_required": ["campaign_metrics", "delivery_logs"], "analyzer": "pacing_analyzer"},
        {"step_id": "s05", "description": "Analyze line-item and creative-level spend distribution", "data_required": ["delivery_logs"], "analyzer": "segment_analyzer"},
    ],
}

_CAMPAIGN_PATTERN = re.compile(r"\b(C\d{2,})\b", re.IGNORECASE)
_INVENTORY_PATTERN = re.compile(r"\b(INV\d{2,})\b", re.IGNORECASE)
_REGION_PATTERN = re.compile(
    r"\b(US|UK|EMEA|APAC|LATAM|NA|EU|ASIA|AMER|EUROPE|CANADA|AUSTRALIA|JAPAN|GERMANY|FRANCE|BRAZIL|INDIA)\b",
    re.IGNORECASE,
)
_TIME_PATTERN = re.compile(
    r"(?:last|past|previous)\s+(\d+)\s*(day|days|week|weeks|month|months)",
    re.IGNORECASE,
)
_DATE_RANGE_PATTERN = re.compile(
    r"(?:from|between)\s+(\d{4}[-/]\d{1,2}[-/]\d{1,2})\s*(?:to|and)\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
    re.IGNORECASE,
)


# ── Issue classifier ──────────────────────────────────────────────────────────

def _classify_issue(text: str) -> str:
    """Classify the question text into one of the 9 issue types.

    Uses keyword matching + fallback regex heuristics. Returns the best-matching
    issue type, defaulting to *underdelivery* when nothing clearly matches.
    """
    lower = text.lower()
    scores: Dict[str, int] = {}

    for issue_type, keywords in _KEYWORD_MAP.items():
        score = 0
        for kw in keywords:
            if kw in lower:
                score += 1
        if score > 0:
            scores[issue_type] = score

    if scores:
        return max(scores, key=scores.get)

    # Regex heuristics as second pass
    if re.search(r"\b(campaign|delivery|serve)\b", lower) and re.search(r"\b(why|issue|problem|drop|slow)\b", lower):
        return "underdelivery"
    if re.search(r"\b(click|ctr|creative|fatigue)\b", lower):
        return "ctr_drop"
    if re.search(r"\bfill\b", lower):
        return "fill_rate_drop"
    if re.search(r"\b(inventory|supply|placement|publisher)\b", lower):
        return "inventory_failure"
    if re.search(r"\b(revenue|rpm|earnings|cpm)\b", lower):
        return "revenue_decline"
    if re.search(r"\bpacing\b", lower):
        return "pacing_issue"
    if re.search(r"\b(forecast|projection|predict|will)\b", lower):
        return "forecast_risk"
    if re.search(r"\b(bid|win rate|auction|cpm)\b", lower):
        return "bid_competitiveness"
    if re.search(r"\b(budget|spend|exhaust|deplet|overrun)\b", lower):
        return "budget_exhaustion"

    return "underdelivery"


def _extract_entities(text: str) -> List[Entity]:
    """Extract campaign IDs, inventory IDs, and region mentions from text."""
    entities: List[Entity] = []
    seen: set = set()

    for match in _CAMPAIGN_PATTERN.finditer(text):
        val = match.group(1).upper()
        if val not in seen:
            seen.add(val)
            entities.append(Entity(type="campaign", value=val, raw_text=match.group(0)))

    for match in _INVENTORY_PATTERN.finditer(text):
        val = match.group(1).upper()
        if val not in seen:
            seen.add(val)
            entities.append(Entity(type="inventory", value=val, raw_text=match.group(0)))

    for match in _REGION_PATTERN.finditer(text):
        val = match.group(1).upper()
        key = f"region:{val}"
        if key not in seen:
            seen.add(key)
            entities.append(Entity(type="region", value=val, raw_text=match.group(0)))

    return entities


def _extract_time_range(text: str) -> TimeRange:
    """Extract or derive a time range from the question text."""
    now = datetime.utcnow()

    match = _DATE_RANGE_PATTERN.search(text)
    if match:
        return TimeRange(start=match.group(1), end=match.group(2), relative="custom")

    match = _TIME_PATTERN.search(text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2).lower()
        if unit in ("day", "days"):
            delta = timedelta(days=amount)
            rel = f"last_{amount}_days"
        elif unit in ("week", "weeks"):
            delta = timedelta(weeks=amount)
            rel = f"last_{amount}_weeks"
        elif unit in ("month", "months"):
            delta = timedelta(days=amount * 30)
            rel = f"last_{amount}_months"
        else:
            delta = timedelta(days=7)
            rel = "last_7_days"
        start = (now - delta).strftime("%Y-%m-%d")
        end = now.strftime("%Y-%m-%d")
        return TimeRange(start=start, end=end, relative=rel)

    # Default: last 7 days
    start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    return TimeRange(start=start, end=end, relative="last_7_days")


def _build_steps(issue_type: str) -> List[InvestigationStep]:
    """Build the list of investigation steps for a given issue type."""
    templates = _STEP_TEMPLATES.get(issue_type, _STEP_TEMPLATES["underdelivery"])
    return [
        InvestigationStep(**tmpl)
        for tmpl in templates
    ]


# ── Planner class ─────────────────────────────────────────────────────────────

class InvestigationPlanner:
    """Classifies operational questions and produces structured investigation plans."""

    @staticmethod
    def analyze_question(text: str) -> InvestigationPlan:
        """Analyse a natural-language question and produce a structured InvestigationPlan.

        Args:
            text: Natural-language question about ad delivery, e.g.
                  *"Why is campaign C123 underdelivering?"*

        Returns:
            InvestigationPlan with classified issue type, extracted entities,
            resolved time range, and a list of investigation steps.
        """
        if not text or not text.strip():
            text = "General delivery investigation"

        issue_type = _classify_issue(text)
        entities = _extract_entities(text)
        time_range = _extract_time_range(text)
        steps = _build_steps(issue_type)

        return InvestigationPlan(
            issue_type=issue_type,
            entities=entities,
            time_range=time_range,
            steps=steps,
            raw_question=text.strip(),
        )
