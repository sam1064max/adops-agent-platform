"""Hypothesis ranker - scores and sorts hypotheses by relevance and strength."""

from __future__ import annotations

import logging
from typing import Dict, List

from src.investigation.evidence_collector import Evidence, EvidenceCollection
from src.investigation.hypothesis_generator import Hypothesis

logger = logging.getLogger(__name__)


# ── Severity weights per category ─────────────────────────────────────────────

_IMPACT_WEIGHTS: Dict[str, float] = {
    "inventory_shortage": 0.9,
    "budget_exhaustion": 0.85,
    "auction_competitiveness": 0.8,
    "creative_fatigue": 0.7,
    "geo_constraint": 0.6,
    "audience_mismatch": 0.65,
    "bid_strategy": 0.7,
    "frequency_capping": 0.5,
    "general": 0.3,
}


class HypothesisRanker:
    """Ranks hypotheses by composite score: confidence × impact × evidence strength.

    Returns the top 3-5 hypotheses sorted by descending score.
    """

    @staticmethod
    def rank_hypotheses(
        hypotheses: List[Hypothesis],
        evidence_collection: EvidenceCollection,
    ) -> List[Hypothesis]:
        """Sort hypotheses by a composite relevance score.

        Scoring formula:
            score = confidence * 0.40
                  + impact_weight * 0.35
                  + evidence_strength * 0.25

        where *evidence_strength* is the fraction of available evidence metrics
        that are referenced by the hypothesis.

        Args:
            hypotheses: List of hypotheses from HypothesisGenerator.
            evidence_collection: The evidence collection for cross-referencing.

        Returns:
            Sorted list of hypotheses (highest score first), limited to top 5.
        """
        if not hypotheses:
            return hypotheses

        total_evidence_metrics = len(set(
            e.metric for e in evidence_collection.evidence_items
        )) or 1

        scored: List[Hypothesis] = []
        for h in hypotheses:
            impact = _IMPACT_WEIGHTS.get(h.category, 0.5)
            evidence_strength = min(
                len(h.evidence_refs) / total_evidence_metrics, 1.0
            ) if total_evidence_metrics > 0 else 0.0

            score = (
                h.confidence * 0.40
                + impact * 0.35
                + evidence_strength * 0.25
            )

            h.confidence = round(score, 4)
            scored.append(h)

        scored.sort(key=lambda x: x.confidence, reverse=True)
        return scored[:5]
