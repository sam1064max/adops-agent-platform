"""Root cause engine - synthesises primary cause from ranked hypotheses and evidence."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from src.investigation.evidence_collector import Evidence, EvidenceCollection
from src.investigation.hypothesis_generator import Hypothesis

logger = logging.getLogger(__name__)


# ── Root cause result model ───────────────────────────────────────────────────

class RootCauseResult(BaseModel):
    """The outcome of root-cause analysis."""
    primary_cause: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    contributing_factors: List[str] = Field(default_factory=list)
    evidence_summary: str = ""
    supporting_metrics: Dict[str, Any] = Field(default_factory=dict)
    primary_category: str = ""


# ── Category-to-narrative mapping ─────────────────────────────────────────────

_CAUSE_NARRATIVES: Dict[str, str] = {
    "inventory_shortage": (
        "The primary root cause is a shortage of available inventory. "
        "Supply from one or more key placement sources has contracted, "
        "reducing the total number of ad opportunities the campaign can bid on. "
        "This may be due to publisher integration issues, seasonal supply drops, "
        "or technical problems on the exchange side."
    ),
    "geo_constraint": (
        "The primary root cause is overly restrictive geo-targeting. "
        "Delivery is being constrained in specific regions where inventory "
        "availability or fill rates are insufficient to meet campaign goals."
    ),
    "creative_fatigue": (
        "The primary root cause is creative fatigue. The same creative assets "
        "have been served to the audience repeatedly, causing CTR to decline "
        "as users become desensitised. Refreshing creative or rotating in new "
        "variants should re-engage the audience."
    ),
    "budget_exhaustion": (
        "The primary root cause is budget exhaustion or poor budget pacing. "
        "The campaign is consuming its budget faster than planned, leading to "
        "early spend depletion or daily cap throttling that reduces delivery."
    ),
    "audience_mismatch": (
        "The primary root cause is audience targeting mismatch. One or more "
        "audience segments are underperforming significantly compared to the "
        "campaign average, indicating that the targeting parameters may need "
        "refinement or exclusion adjustments."
    ),
    "auction_competitiveness": (
        "The primary root cause is declining auction competitiveness. "
        "Win rates have dropped as other bidders are outbidding the campaign. "
        "This may require bid price adjustments, floor price negotiation, or "
        "inventory path optimisation."
    ),
    "bid_strategy": (
        "The primary root cause is suboptimal bid strategy. Current bid prices "
        "may not align with floor prices or competitive dynamics, causing the "
        "campaign to lose auctions or pay inefficiently high CPMs."
    ),
    "frequency_capping": (
        "The primary root cause is frequency capping or audience saturation. "
        "High average frequency indicates the same users are being reached "
        "repeatedly, which diminishes returns and may trigger cap throttling."
    ),
    "general": (
        "No specific root cause could be determined with high confidence. "
        "The campaign exhibits mild anomalies that do not clearly point to "
        "a single operational failure. Further manual investigation is advised."
    ),
}


class RootCauseEngine:
    """Determines the primary root cause from ranked hypotheses and evidence.

    Selects the highest-ranked hypothesis as the primary cause and aggregates
    supporting evidence from lower-ranked hypotheses into contributing factors.
    """

    @staticmethod
    def determine_root_cause(
        hypotheses: List[Hypothesis],
        evidence_collection: EvidenceCollection,
    ) -> RootCauseResult:
        """Synthesize a primary root cause narrative from ranked hypotheses.

        Args:
            hypotheses: Ranked list of hypotheses (highest confidence first).
            evidence_collection: The full evidence collection for metric extraction.

        Returns:
            RootCauseResult with primary cause, confidence, contributing factors,
            evidence summary, and supporting metrics.
        """
        if not hypotheses:
            return RootCauseResult(
                primary_cause="No hypotheses were generated. Unable to determine root cause.",
                confidence=0.0,
                contributing_factors=[],
                evidence_summary="No evidence available.",
                supporting_metrics={},
                primary_category="general",
            )

        primary = hypotheses[0]
        narrative = _CAUSE_NARRATIVES.get(primary.category, primary.description)
        narrative = f"{narrative.strip()}" if narrative else primary.description

        # Build contributing factors from secondary hypotheses (rank 2+)
        contributing_factors: List[str] = []
        for h in hypotheses[1:]:
            if h.confidence >= 0.2:
                contributing_factors.append(
                    f"[{h.category}] {h.description[:200]}"
                )

        # Build evidence summary
        evidence_lines: List[str] = []
        for e in evidence_collection.evidence_items[:10]:
            evidence_lines.append(
                f"- {e.metric}: current={e.current_value:.2f}, "
                f"historical={e.historical_value:.2f}, "
                f"delta={e.delta:+.2f} {e.unit} "
                f"(confidence: {e.confidence:.2f})"
            )
        evidence_summary = "\n".join(evidence_lines) if evidence_lines else "No evidence metrics available."

        # Collect supporting metrics from evidence
        supporting_metrics: Dict[str, Any] = {}
        for e in evidence_collection.evidence_items:
            key = e.metric
            if key not in supporting_metrics:
                supporting_metrics[key] = {
                    "current": round(e.current_value, 4),
                    "historical": round(e.historical_value, 4),
                    "delta": round(e.delta, 4),
                    "unit": e.unit,
                    "confidence": round(e.confidence, 4),
                }

        confidence = max(
            hypotheses[0].confidence,
            sum(h.confidence for h in hypotheses) / max(len(hypotheses), 1) * 0.5,
        )
        confidence = min(round(confidence, 4), 1.0)

        return RootCauseResult(
            primary_cause=narrative,
            confidence=confidence,
            contributing_factors=contributing_factors,
            evidence_summary=evidence_summary,
            supporting_metrics=supporting_metrics,
            primary_category=primary.category,
        )
