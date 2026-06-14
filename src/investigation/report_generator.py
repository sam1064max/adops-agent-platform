"""Report generator - produces structured, human-readable investigation reports."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from src.investigation.evidence_collector import Evidence, EvidenceCollection
from src.investigation.hypothesis_generator import Hypothesis
from src.investigation.recommendation_engine import Recommendation
from src.investigation.root_cause_engine import RootCauseResult

logger = logging.getLogger(__name__)


# ── Report model ──────────────────────────────────────────────────────────────

class EvidenceTableRow(BaseModel):
    """A row in the evidence comparison table."""
    metric: str
    current_value: str
    historical_value: str
    delta: str
    unit: str
    verdict: str = ""


class InvestigationReport(BaseModel):
    """Complete investigation report with narrative and structured data."""
    summary: str = ""
    primary_cause: str = ""
    confidence: float = 0.0
    evidence_table: List[EvidenceTableRow] = Field(default_factory=list)
    supporting_factors: List[str] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    risk_level: str = "medium"
    report_id: str = ""
    generated_at: str = ""


# ── Risk assessment ───────────────────────────────────────────────────────────

def _assess_risk(confidence: float, root_cause: RootCauseResult) -> str:
    """Determine risk level based on root cause category and confidence."""
    high_risk_categories = {
        "inventory_shortage", "budget_exhaustion", "auction_competitiveness",
    }
    medium_risk_categories = {
        "creative_fatigue", "geo_constraint", "bid_strategy",
    }

    if root_cause.primary_category in high_risk_categories and confidence > 0.6:
        return "high"
    if root_cause.primary_category in high_risk_categories:
        return "high"
    if root_cause.primary_category in medium_risk_categories:
        return "medium"
    if confidence < 0.3:
        return "low"
    return "medium"


def _format_value(val: float, unit: str) -> str:
    """Format a metric value with appropriate precision."""
    if unit in ("pct", "score", "flag"):
        return f"{val:.2f}"
    if unit in ("usd", "cpm"):
        return f"${val:.4f}"
    if unit in ("impressions", "days"):
        return f"{val:,.0f}"
    return f"{val:.4f}"


def _verdict(delta: float, unit: str) -> str:
    """Determine a qualitative verdict for a delta."""
    if abs(delta) < 1.0:
        return "stable"
    if delta > 0:
        return "improving" if unit in ("pct",) or abs(delta) > 5 else "slightly improving"
    return "declining" if unit in ("pct",) or abs(delta) < -5 else "slightly declining"


class ReportGenerator:
    """Generates structured investigation reports from root cause and evidence."""

    @staticmethod
    def generate_report(
        question: str,
        root_cause: RootCauseResult,
        recommendations: List[Recommendation],
        evidence_collection: EvidenceCollection,
    ) -> InvestigationReport:
        """Produce a complete InvestigationReport.

        Args:
            question: The original investigation question.
            root_cause: Analysed root cause.
            recommendations: Generated recommendations.
            evidence_collection: Collected evidence.

        Returns:
            InvestigationReport with narrative summary, evidence table, and risk level.
        """
        now = datetime.utcnow()
        report_id = f"INV-{now.strftime('%Y%m%d-%H%M%S')}-{hash(question) % 10000:04d}"

        # ── Summary ────────────────────────────────────────────────────
        entity_summary = ""
        for e in evidence_collection.plan.entities:
            entity_summary = f"{entity_summary}, {e.type}={e.value}" if entity_summary else f"{e.type}={e.value}"

        summary_parts = [
            f"Investigation Report for: {question}",
        ]
        if entity_summary:
            summary_parts.append(f"Entities identified: {entity_summary}")
        summary_parts.append(
            f"Issue type classified as: {evidence_collection.plan.issue_type}"
        )
        summary_parts.append(
            f"Time range analysed: {evidence_collection.plan.time_range.start} "
            f"to {evidence_collection.plan.time_range.end}"
        )
        summary = " | ".join(summary_parts)

        # ── Evidence table ─────────────────────────────────────────────
        evidence_table: List[EvidenceTableRow] = []
        for e in evidence_collection.evidence_items:
            # Deduplicate by metric name, keep first occurrence
            if any(row.metric == e.metric for row in evidence_table):
                continue
            delta_formatted = f"{e.delta:+.2f}" if abs(e.delta) > 0.01 else "0.00"
            row = EvidenceTableRow(
                metric=e.metric,
                current_value=_format_value(e.current_value, e.unit),
                historical_value=_format_value(e.historical_value, e.unit),
                delta=delta_formatted,
                unit=e.unit,
                verdict=_verdict(e.delta, e.unit),
            )
            evidence_table.append(row)

        # Risk level
        risk_level = _assess_risk(root_cause.confidence, root_cause)

        return InvestigationReport(
            summary=summary,
            primary_cause=root_cause.primary_cause,
            confidence=root_cause.confidence,
            evidence_table=evidence_table,
            supporting_factors=root_cause.contributing_factors,
            recommendations=recommendations,
            risk_level=risk_level,
            report_id=report_id,
            generated_at=now.isoformat(),
        )
