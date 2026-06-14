"""Recommendation engine - generates operational actions based on root cause."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from src.investigation.evidence_collector import Evidence, EvidenceCollection
from src.investigation.root_cause_engine import RootCauseResult

logger = logging.getLogger(__name__)


# ── Recommendation model ──────────────────────────────────────────────────────

class Recommendation(BaseModel):
    """An operational recommendation to address a root cause."""
    action: str
    expected_impact: str = ""
    priority: str = "medium"  # high / medium / low
    type: str = ""  # inventory / targeting / budget / creative / auction


# ── Recommendation templates ──────────────────────────────────────────────────

_RECOMMENDATIONS: Dict[str, List[Dict[str, str]]] = {
    "inventory_shortage": [
        {
            "action": "Expand inventory pool to include adjacent channels and ad formats",
            "expected_impact": "Increase available supply by 20-40% by opening new placements",
            "priority": "high",
            "type": "inventory",
        },
        {
            "action": "Negotiate programmatic guaranteed (PG) deals with top publishers for reserved inventory",
            "expected_impact": "Secure 10-25% more guaranteed impressions at stable CPMs",
            "priority": "high",
            "type": "inventory",
        },
        {
            "action": "Enable automatic inventory expansion via exchange preferred deals",
            "expected_impact": "Improve fill rate by 15-30% through broader supply access",
            "priority": "medium",
            "type": "inventory",
        },
    ],
    "geo_constraint": [
        {
            "action": "Relax geo targeting from DMA-level to state-level or regional scope",
            "expected_impact": "Expand reachable audience by 30-50% in constrained regions",
            "priority": "high",
            "type": "targeting",
        },
        {
            "action": "Add top-performing regions while pausing low-fill geos",
            "expected_impact": "Improve overall fill rate by 10-20% by reallocating budget",
            "priority": "medium",
            "type": "targeting",
        },
        {
            "action": "Review regional bid multipliers and adjust floor prices per geo",
            "expected_impact": "Increase win rates in tight supply regions by 15-25%",
            "priority": "medium",
            "type": "auction",
        },
    ],
    "creative_fatigue": [
        {
            "action": "Rotate in 3-5 fresh creative variants split by messaging and CTA",
            "expected_impact": "Recover CTR by 15-30% within the first week of rotation",
            "priority": "high",
            "type": "creative",
        },
        {
            "action": "Reduce frequency cap from current level to 3 impressions per user per day",
            "expected_impact": "Reduce audience saturation and improve per-impression engagement",
            "priority": "high",
            "type": "creative",
        },
        {
            "action": "A/B test new headlines, imagery, and CTAs against fatigued creatives",
            "expected_impact": "Identify winning creative direction with 90% statistical confidence",
            "priority": "medium",
            "type": "creative",
        },
    ],
    "budget_exhaustion": [
        {
            "action": "Reallocate budget from underperforming line items to top-performing ones",
            "expected_impact": "Extend campaign runway by 20-35% without increasing total budget",
            "priority": "high",
            "type": "budget",
        },
        {
            "action": "Adjust daily budget caps to spread spend evenly across remaining flight days",
            "expected_impact": "Prevent premature budget depletion and smooth delivery pacing",
            "priority": "high",
            "type": "budget",
        },
        {
            "action": "Request additional budget allocation from advertiser for high-ROAS campaigns",
            "expected_impact": "Capture incremental conversions during peak performance periods",
            "priority": "medium",
            "type": "budget",
        },
    ],
    "audience_mismatch": [
        {
            "action": "Exclude underperforming audience segments with >30% CTR deviation",
            "expected_impact": "Improve overall campaign CTR by 10-20% by removing low performers",
            "priority": "high",
            "type": "targeting",
        },
        {
            "action": "Refine audience targeting using first-party data and lookalike modelling",
            "expected_impact": "Increase audience relevance score by 15-25%",
            "priority": "medium",
            "type": "targeting",
        },
    ],
    "auction_competitiveness": [
        {
            "action": "Increase bid floor tolerance by 15% to remain competitive in dense auctions",
            "expected_impact": "Improve win rate by 10-20% in competitive inventory segments",
            "priority": "high",
            "type": "auction",
        },
        {
            "action": "Review and optimise supply path to reduce intermediary layers",
            "expected_impact": "Reduce bid duplication and improve win rate by 5-15%",
            "priority": "medium",
            "type": "auction",
        },
        {
            "action": "Enable auction insights reporting to identify top competing buyers",
            "expected_impact": "Provide competitive intelligence for strategic bid adjustments",
            "priority": "medium",
            "type": "auction",
        },
    ],
    "bid_strategy": [
        {
            "action": "Adjust bid price to align with floor price + 20% premium for priority inventory",
            "expected_impact": "Increase win rate on premium inventory by 15-25%",
            "priority": "high",
            "type": "auction",
        },
        {
            "action": "Implement bid shading optimisation to avoid overpaying in low-competition auctions",
            "expected_impact": "Reduce average CPM by 10-15% while maintaining win rate",
            "priority": "medium",
            "type": "budget",
        },
    ],
    "frequency_capping": [
        {
            "action": "Reduce frequency cap from current to 3 impressions/user/day and monitor impact",
            "expected_impact": "Improve CTR by 10-20% by reducing overexposure",
            "priority": "high",
            "type": "creative",
        },
        {
            "action": "Enable cross-device frequency management to prevent over-saturation",
            "expected_impact": "Reach 20-30% more unique users at same impression volume",
            "priority": "medium",
            "type": "targeting",
        },
    ],
    "general": [
        {
            "action": "Review campaign setup and targeting configuration for basic errors",
            "expected_impact": "Identify configuration issues that may impact delivery",
            "priority": "medium",
            "type": "targeting",
        },
        {
            "action": "Cross-reference delivery logs with publisher outage reports",
            "expected_impact": "Rule out external factors affecting campaign performance",
            "priority": "low",
            "type": "inventory",
        },
        {
            "action": "Escalate to ad operations team for manual investigation",
            "expected_impact": "Apply human expertise to diagnose subtle or compound issues",
            "priority": "low",
            "type": "inventory",
        },
    ],
}


class RecommendationEngine:
    """Generates operational recommendations from root cause analysis results."""

    @staticmethod
    def generate_recommendations(
        root_cause: RootCauseResult,
        evidence_collection: EvidenceCollection,
    ) -> List[Recommendation]:
        """Generate actionable recommendations based on root cause and evidence.

        Args:
            root_cause: The determined root cause from RootCauseEngine.
            evidence_collection: Evidence for context-aware recommendation tuning.

        Returns:
            List of Recommendation objects, sorted by priority.
        """
        category = root_cause.primary_category
        templates = _RECOMMENDATIONS.get(category, _RECOMMENDATIONS["general"])

        recommendations: List[Recommendation] = []
        for t in templates:
            recommendations.append(Recommendation(**t))

        # Add supplementary recommendations from contributing factors
        for factor in root_cause.contributing_factors:
            cat_match = None
            for known_cat in _RECOMMENDATIONS:
                if f"[{known_cat}]" in factor:
                    cat_match = known_cat
                    break
            if cat_match and cat_match != category:
                for t in _RECOMMENDATIONS[cat_match][:1]:
                    rec = Recommendation(**t)
                    rec.action = f"[Supplementary] {rec.action}"
                    recommendations.append(rec)

        _priority_order = {"high": 0, "medium": 1, "low": 2}
        recommendations.sort(key=lambda r: _priority_order.get(r.priority, 99))

        return recommendations
