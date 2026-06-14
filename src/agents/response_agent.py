"""Response agent - final synthesis and formatting for the AdOps pipeline."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

from src.api.metrics import response_latency
from src.models.schemas import EscalationLevel, IssueType, QueryResponse

logger = logging.getLogger(__name__)

_ESCALATION_THRESHOLDS = {
    "fraud_signal": EscalationLevel.HIGH,
    "brand_safety": EscalationLevel.HIGH,
    "budget_depletion": EscalationLevel.MEDIUM,
    "inventory_shortage": EscalationLevel.MEDIUM,
    "delivery_underperformance": EscalationLevel.LOW,
    "pacing_anomaly": EscalationLevel.LOW,
    "creative_fatigue": EscalationLevel.LOW,
    "geo_mismatch": EscalationLevel.LOW,
    "viewability_drop": EscalationLevel.LOW,
    "general": EscalationLevel.LOW,
}


class ResponseAgent:
    """Converts analysis output into the final QueryResponse schema.

    Handles escalation-level assignment and confidence-based gating.
    """

    @response_latency.time()
    def synthesise(
        self,
        query_text: str,
        classified: Dict[str, Any],
        retrieval_context: Dict[str, Any],
        analysis: Dict[str, Any],
    ) -> QueryResponse:
        """Build the final QueryResponse from the pipeline outputs.

        Args:
            query_text: Original user query.
            classified: Output from QueryAgent.classify_issue().
            retrieval_context: Output from RetrievalAgent.retrieve().
            analysis: Output from AnalysisAgent.analyse().

        Returns:
            Populated QueryResponse.
        """
        issue_type_str = classified.get("issue_type", "general")
        try:
            issue_type = IssueType(issue_type_str)
        except ValueError:
            issue_type = IssueType.GENERAL

        escalation = _ESCALATION_THRESHOLDS.get(
            issue_type_str, EscalationLevel.LOW
        )
        confidence = analysis.get("confidence", 0.0)

        # Bump escalation for high-confidence critical signals
        if confidence >= 0.8 and issue_type_str in (
            "fraud_signal",
            "brand_safety",
        ):
            escalation = EscalationLevel.CRITICAL

        # Extract entity IDs for the response
        entity_ids = [
            e.get("value", "")
            for e in classified.get("entities", [])
            if e.get("value")
        ]

        response = QueryResponse(
            issue_type=issue_type,
            entities=entity_ids,
            summary=self._build_summary(issue_type_str, analysis),
            evidence=analysis.get("evidence", []),
            root_cause=analysis.get("root_cause"),
            confidence=confidence,
            recommended_actions=analysis.get("recommended_actions", []),
            escalation=escalation,
        )

        logger.info(
            "Response synthesised: issue=%s escalation=%s confidence=%.2f",
            issue_type.value,
            escalation.value,
            confidence,
        )
        return response

    @staticmethod
    def _build_summary(issue_type: str, analysis: Dict[str, Any]) -> str:
        """Create a concise plain-language summary."""
        root_cause = analysis.get("root_cause", "No root cause identified.")
        confidence = analysis.get("confidence", 0.0)
        n_evidence = len(analysis.get("evidence", []))

        return (
            f"Detected {issue_type.replace('_', ' ')}. "
            f"{root_cause} "
            f"Confidence: {confidence:.0%} based on {n_evidence} evidence point(s)."
        )
