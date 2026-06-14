"""Hypothesis generator - forms causal hypotheses from collected evidence."""

from __future__ import annotations

import logging
from typing import Dict, List

from pydantic import BaseModel, Field

from src.investigation.evidence_collector import Evidence, EvidenceCollection

logger = logging.getLogger(__name__)


# ── Hypothesis model ──────────────────────────────────────────────────────────

class Hypothesis(BaseModel):
    """A single causal hypothesis derived from evidence."""
    hypothesis_id: str
    description: str
    evidence_refs: List[str] = Field(default_factory=list, description="Metric names supporting this hypothesis")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    category: str = ""


# ── Detection thresholds ──────────────────────────────────────────────────────

_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "inventory_shortage": {"fill_rate_delta": -20.0, "inventory_health": 40.0},
    "geo_constraint": {"regional_issue_count": 1},
    "creative_fatigue": {"creative_fatigue_score": 0.15, "ctr_delta": -15.0},
    "budget_exhaustion": {"budget_consumption": 90.0, "pace_delta": -20.0},
    "audience_mismatch": {"audience_deviation": -30.0},
    "auction_competitiveness": {"win_rate_delta": -20.0},
    "bid_strategy": {"cpm_delta": 15.0, "floor_gap": 0.5},
    "frequency_capping": {"avg_frequency": 8.0},
}


class HypothesisGenerator:
    """Generates causal hypotheses by analysing evidence deltas against thresholds.

    Maps evidence metric deltas to hypothesis categories using deterministic
    rules. Each hypothesis is scored based on how strongly the evidence
    exceeds the detection threshold.
    """

    @staticmethod
    def generate_hypotheses(evidence_collection: EvidenceCollection) -> List[Hypothesis]:
        """Generate hypotheses from collected evidence.

        Args:
            evidence_collection: Normalized evidence from EvidenceCollector.

        Returns:
            List of Hypothesis objects with confidence scores and evidence refs.
        """
        evidence_map: Dict[str, List[Evidence]] = {}
        for item in evidence_collection.evidence_items:
            evidence_map.setdefault(item.metric, []).append(item)

        hypotheses: List[Hypothesis] = []
        idx = 0

        # ── Inventory shortage hypothesis ──────────────────────────────
        fill_deltas = [e.delta for e in evidence_map.get("fill_rate", [])]
        fill_drop = min(fill_deltas) if fill_deltas else 0.0
        health_scores = [e.current_value for e in evidence_map.get("inventory_health", [])]
        health_val = min(health_scores) if health_scores else 100.0

        if fill_drop < _THRESHOLDS["inventory_shortage"]["fill_rate_delta"] or health_val < _THRESHOLDS["inventory_shortage"]["inventory_health"]:
            fill_strength = abs(fill_drop - (-20.0)) / 80.0 if fill_drop < -20.0 else 0.0
            health_strength = (40.0 - health_val) / 40.0 if health_val < 40.0 else 0.0
            confidence = min(max(fill_strength, health_strength), 1.0) * 0.8 + 0.1
            refs = []
            if fill_deltas:
                refs.append("fill_rate")
            if health_scores:
                refs.append("inventory_health")
            idx += 1
            hypotheses.append(Hypothesis(
                hypothesis_id=f"H{idx:02d}",
                description=(
                    f"Inventory shortage detected: fill rate delta {fill_drop:.1f}%, "
                    f"inventory health {health_val:.1f}/100. Supply may be constrained "
                    f"due to publisher availability or technical integration issues."
                ),
                evidence_refs=refs,
                confidence=round(confidence, 4),
                category="inventory_shortage",
            ))

        # ── Auction competitiveness hypothesis ─────────────────────────
        win_deltas = [e.delta for e in evidence_map.get("win_rate", [])]
        win_drop = min(win_deltas) if win_deltas else 0.0

        if win_drop < _THRESHOLDS["auction_competitiveness"]["win_rate_delta"]:
            strength = abs(win_drop - (-20.0)) / 80.0 if win_drop < -20.0 else 0.0
            confidence = min(strength, 1.0) * 0.75 + 0.15
            idx += 1
            hypotheses.append(Hypothesis(
                hypothesis_id=f"H{idx:02d}",
                description=(
                    f"Auction competitiveness declining: win rate delta {win_drop:.1f}%. "
                    f"Campaign bids are losing to competitors, possibly due to "
                    f"aggressive floor prices or increased auction density."
                ),
                evidence_refs=["win_rate"],
                confidence=round(confidence, 4),
                category="auction_competitiveness",
            ))

        # ── Creative fatigue hypothesis ────────────────────────────────
        fatigue_scores = [e.current_value for e in evidence_map.get("creative_fatigue_score", [])]
        fatigue_val = max(fatigue_scores) if fatigue_scores else 0.0
        ctr_deltas = [e.delta for e in evidence_map.get("ctr", [])]
        ctr_drop = min(ctr_deltas) if ctr_deltas else 0.0

        if fatigue_val > _THRESHOLDS["creative_fatigue"]["creative_fatigue_score"] or ctr_drop < _THRESHOLDS["creative_fatigue"]["ctr_delta"]:
            fatigue_strength = (fatigue_val - 0.15) / 0.85 if fatigue_val > 0.15 else 0.0
            ctr_strength = abs(ctr_drop - (-15.0)) / 85.0 if ctr_drop < -15.0 else 0.0
            confidence = min(max(fatigue_strength, ctr_strength), 1.0) * 0.7 + 0.2
            refs = []
            if fatigue_scores:
                refs.append("creative_fatigue_score")
            if ctr_deltas:
                refs.append("ctr")
            idx += 1
            hypotheses.append(Hypothesis(
                hypothesis_id=f"H{idx:02d}",
                description=(
                    f"Creative fatigue suspected: fatigue score {fatigue_val:.2f}, "
                    f"CTR delta {ctr_drop:.1f}%. Audience may be experiencing ad "
                    f"blindness from overexposure to the same creative assets."
                ),
                evidence_refs=refs,
                confidence=round(confidence, 4),
                category="creative_fatigue",
            ))

        # ── Budget exhaustion hypothesis ───────────────────────────────
        budget_vals = [e.current_value for e in evidence_map.get("budget_consumption_pct", [])]
        budget_consumed = max(budget_vals) if budget_vals else 0.0
        pace_deltas = [e.delta for e in evidence_map.get("pace_pct", [])]
        pace_drop = min(pace_deltas) if pace_deltas else 0.0

        if budget_consumed > _THRESHOLDS["budget_exhaustion"]["budget_consumption"] or pace_drop < _THRESHOLDS["budget_exhaustion"]["pace_delta"]:
            budget_strength = (budget_consumed - 90.0) / 10.0 if budget_consumed > 90.0 else 0.0
            pace_strength = abs(pace_drop - (-20.0)) / 80.0 if pace_drop < -20.0 else 0.0
            confidence = min(max(budget_strength, pace_strength), 1.0) * 0.8 + 0.1
            refs = []
            if budget_vals:
                refs.append("budget_consumption_pct")
            if pace_deltas:
                refs.append("pace_pct")
            idx += 1
            hypotheses.append(Hypothesis(
                hypothesis_id=f"H{idx:02d}",
                description=(
                    f"Budget exhaustion risk: {budget_consumed:.1f}% consumed, "
                    f"pacing delta {pace_drop:.1f}%. Campaign may be burning "
                    f"budget faster than planned or hitting daily caps."
                ),
                evidence_refs=refs,
                confidence=round(confidence, 4),
                category="budget_exhaustion",
            ))

        # ── Audience mismatch hypothesis ───────────────────────────────
        audience_evs = [e for e in evidence_collection.evidence_items if e.metric == "audience_mismatch"]
        if audience_evs:
            worst_deviation = min(e.delta for e in audience_evs)
            if worst_deviation < _THRESHOLDS["audience_mismatch"]["audience_deviation"]:
                strength = abs(worst_deviation - (-30.0)) / 70.0 if worst_deviation < -30.0 else 0.0
                confidence = min(strength, 1.0) * 0.65 + 0.2
                idx += 1
                hypotheses.append(Hypothesis(
                    hypothesis_id=f"H{idx:02d}",
                    description=(
                        f"Audience mismatch detected: worst segment deviation "
                        f"{worst_deviation:.1f}%. Targeting settings may be "
                        f"reaching the wrong audience segments."
                    ),
                    evidence_refs=["audience_mismatch"],
                    confidence=round(confidence, 4),
                    category="audience_mismatch",
                ))

        # ── Geo constraint hypothesis ──────────────────────────────────
        regional_issues = [e for e in evidence_collection.evidence_items if e.metric.startswith("regional_")]
        if len(regional_issues) >= _THRESHOLDS["geo_constraint"]["regional_issue_count"]:
            confidence = min(len(regional_issues) * 0.15, 0.8) + 0.1
            regions = set()
            for e in regional_issues:
                r = e.metadata.get("region", "unknown")
                regions.add(r)
            idx += 1
            hypotheses.append(Hypothesis(
                hypothesis_id=f"H{idx:02d}",
                description=(
                    f"Geo targeting constraint affecting delivery in "
                    f"{len(regions)} region(s): {', '.join(sorted(regions))}. "
                    f"Regional fill rate or inventory issues detected."
                ),
                evidence_refs=[e.metric for e in regional_issues],
                confidence=round(confidence, 4),
                category="geo_constraint",
            ))

        # ── Bid strategy hypothesis ────────────────────────────────────
        cpm_vals = [e.delta for e in evidence_map.get("avg_cpm", [])]
        cpm_change = max(cpm_vals) if cpm_vals else 0.0
        floor_vals = [e.current_value for e in evidence_map.get("avg_floor_price", [])]
        avg_floor = max(floor_vals) if floor_vals else 0.0

        if cpm_change > _THRESHOLDS["bid_strategy"]["cpm_delta"] or avg_floor > _THRESHOLDS["bid_strategy"]["floor_gap"]:
            cpm_strength = (cpm_change - 15.0) / 85.0 if cpm_change > 15.0 else 0.0
            floor_strength = avg_floor / 5.0 if avg_floor > 0.5 else 0.0
            confidence = min(max(cpm_strength, floor_strength), 1.0) * 0.6 + 0.2
            idx += 1
            hypotheses.append(Hypothesis(
                hypothesis_id=f"H{idx:02d}",
                description=(
                    f"Bid strategy may need adjustment: CPM changed by "
                    f"{cpm_change:.1f}%, avg floor price ${avg_floor:.2f}. "
                    f"Current bid pricing may not be competitive."
                ),
                evidence_refs=["avg_cpm", "avg_floor_price"],
                confidence=round(confidence, 4),
                category="bid_strategy",
            ))

        # ── Frequency capping hypothesis ───────────────────────────────
        freq_vals = [e.current_value for e in evidence_map.get("avg_frequency", [])]
        avg_freq = max(freq_vals) if freq_vals else 0.0

        if avg_freq > _THRESHOLDS["frequency_capping"]["avg_frequency"]:
            strength = (avg_freq - 8.0) / 12.0 if avg_freq > 8.0 else 0.0
            confidence = min(strength, 1.0) * 0.5 + 0.3
            idx += 1
            hypotheses.append(Hypothesis(
                hypothesis_id=f"H{idx:02d}",
                description=(
                    f"Frequency capping concern: avg {avg_freq:.1f} "
                    f"impressions per user. High frequency may be causing "
                    f"audience saturation and declining engagement."
                ),
                evidence_refs=["avg_frequency"],
                confidence=round(confidence, 4),
                category="frequency_capping",
            ))

        # ── Delivery volume hypothesis (general) ───────────────────────
        vol_deltas = [e.delta for e in evidence_map.get("delivery_volume_trend", [])]
        vol_drop = min(vol_deltas) if vol_deltas else 0.0

        if vol_drop < -30.0:
            strength = abs(vol_drop - (-30.0)) / 70.0 if vol_drop < -30.0 else 0.0
            confidence = min(strength, 1.0) * 0.6 + 0.2
            idx += 1
            hypotheses.append(Hypothesis(
                hypothesis_id=f"H{idx:02d}",
                description=(
                    f"Delivery volume dropped {vol_drop:.1f}% in recent period. "
                    f"Overall delivery capacity may be constrained."
                ),
                evidence_refs=["delivery_volume_trend"],
                confidence=round(confidence, 4),
                category="inventory_shortage",
            ))

        # ── Underdelivery catch-all ────────────────────────────────────
        pace_current = [e.current_value for e in evidence_map.get("pace_pct", [])]
        pace_expected = [e.historical_value for e in evidence_map.get("pace_pct", [])]
        if pace_current and pace_expected:
            pace_ratio = pace_current[0] / pace_expected[0] if pace_expected[0] > 0 else 1.0
            if pace_ratio < 0.7 and not any(h.category in ("budget_exhaustion", "inventory_shortage", "auction_competitiveness") for h in hypotheses):
                confidence = max(0.0, (0.7 - pace_ratio) / 0.7) * 0.6 + 0.2
                idx += 1
                hypotheses.append(Hypothesis(
                    hypothesis_id=f"H{idx:02d}",
                    description=(
                        f"General underdelivery detected: actual pace is "
                        f"{pace_ratio*100:.1f}% of expected. Multiple factors "
                        f"may be contributing to reduced delivery."
                    ),
                    evidence_refs=["pace_pct"],
                    confidence=round(confidence, 4),
                    category="bid_strategy",
                ))

        if not hypotheses:
            idx += 1
            hypotheses.append(Hypothesis(
                hypothesis_id=f"H{idx:02d}",
                description="No significant anomalies detected. Campaign is performing within expected parameters.",
                evidence_refs=[],
                confidence=0.1,
                category="general",
            ))

        return hypotheses
