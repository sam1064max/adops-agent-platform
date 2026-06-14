"""Analysis agent - root cause detection and recommendation generation."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from src.api.metrics import analysis_latency

logger = logging.getLogger(__name__)

# Heuristic keyword-to-action mapping for deterministic fallbacks
_ACTION_MAP: Dict[str, List[str]] = {
    "delivery_underperformance": [
        "Audit creative assets for fatigue and refresh if CTR has declined >20%.",
        "Verify pacing configuration aligns with flight dates.",
        "Check daily caps and frequency caps for over-restriction.",
    ],
    "pacing_anomaly": [
        "Review bid strategy and daily budget allocation.",
        "Confirm deal pacing settings with the publisher.",
        "Consider dayparting adjustments to smooth delivery.",
    ],
    "fraud_signal": [
        "Flag high fraud-score line items for manual review.",
        "Enable pre-bid fraud filtering at the DSP level.",
        "Request publisher-side supply path transparency.",
    ],
    "inventory_shortage": [
        "Expand targeting to additional inventory sources.",
        "Negotiate priority access with key publishers.",
        "Evaluate programmatic guaranteed deals for guaranteed supply.",
    ],
    "creative_fatigue": [
        "Rotate in fresh creative assets.",
        "A/B test new headlines or CTAs.",
        "Reduce frequency cap temporarily while creatives refresh.",
    ],
    "budget_depletion": [
        "Reallocate budget from underperforming campaigns.",
        "Request budget increase from the advertiser.",
        "Pause low-ROAS line items to preserve budget for winners.",
    ],
    "geo_mismatch": [
        "Audit geo-targeting settings at the line-item level.",
        "Exclude regions with zero conversion signal.",
        "Align campaign geo strategy with advertiser KPIs.",
    ],
    "viewability_drop": [
        "Shift spend toward high-viewability placements.",
        "Enable viewability targeting (>=70% IAB standard).",
        "Work with publisher to improve ad placement.",
    ],
    "brand_safety": [
        "Tighten brand-safety exclusion lists.",
        "Enable pre-bid brand-safety filtering.",
        "Audit recent serving logs for problematic domains.",
    ],
}


class AnalysisAgent:
    """Analyses retrieval context and produces structured findings.

    In a full deployment this would invoke an LLM; here we provide
    a deterministic heuristic engine that works offline.
    """

    def __init__(self, db_session_factory: Optional[Callable[..., Session]] = None) -> None:
        self._db_factory = db_session_factory

    @analysis_latency.time()
    def analyse(
        self,
        issue_type: str,
        entities: List[Dict[str, Any]],
        retrieval_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Produce a structured analysis from the issue and context.

        Args:
            issue_type: Classified issue type from QueryAgent.
            entities: Extracted entities list.
            retrieval_context: Output from RetrievalAgent.retrieve().

        Returns:
            Dict with root_cause, confidence, recommended_actions, evidence.
        """
        t0 = time.perf_counter()

        snippets = retrieval_context.get("snippets", [])
        campaign_ctx = retrieval_context.get("campaign_context", [])
        inventory_ctx = retrieval_context.get("inventory_context", [])

        evidence = self._collect_evidence(snippets, campaign_ctx, inventory_ctx)
        root_cause = self._infer_root_cause(issue_type, evidence)
        confidence = self._compute_confidence(issue_type, evidence, campaign_ctx)
        actions = _ACTION_MAP.get(issue_type, ["Review campaign data manually."])

        elapsed = time.perf_counter() - t0
        logger.info(
            "Analysis complete: issue=%s confidence=%.2f evidence_count=%d in %.3fs",
            issue_type,
            confidence,
            len(evidence),
            elapsed,
        )

        return {
            "root_cause": root_cause,
            "confidence": round(confidence, 4),
            "recommended_actions": actions,
            "evidence": evidence,
        }

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _collect_evidence(
        snippets: List[Dict[str, Any]],
        campaigns: List[Dict[str, Any]],
        inventory: List[Dict[str, Any]],
    ) -> List[str]:
        evidence: List[str] = []

        for s in snippets[:5]:
            content = s.get("content", "").strip()
            if content:
                evidence.append(f"[KB] {content[:300]}")

        for c in campaigns:
            parts = [f"Campaign {c['campaign_id']}"]
            if c.get("name"):
                parts.append(f'"{c["name"]}"')
            for metric in ("impressions", "clicks", "spend"):
                val = c.get(metric, 0)
                if val:
                    parts.append(f"{metric}={val}")
            if c.get("status"):
                parts.append(f"status={c['status']}")
            evidence.append("[DB] " + " | ".join(parts))

        for inv in inventory:
            parts = [f"Inventory {inv['inventory_id']}"]
            if inv.get("publisher"):
                parts.append(f"publisher={inv['publisher']}")
            for metric in ("viewability_rate", "floor_price"):
                val = inv.get(metric, 0)
                if val:
                    parts.append(f"{metric}={val}")
            evidence.append("[DB] " + " | ".join(parts))

        return evidence

    @staticmethod
    def _infer_root_cause(issue_type: str, evidence: List[str]) -> str:
        """Return a human-readable root-cause hypothesis."""
        base = _ACTION_MAP.get(issue_type, ["general issue"])[0]
        evidence_hint = ""
        for e in evidence:
            if "[DB]" in e:
                evidence_hint = e
                break
        if evidence_hint:
            return f"{base} Based on data: {evidence_hint}"
        return base

    @staticmethod
    def _compute_confidence(
        issue_type: str,
        evidence: List[str],
        campaigns: List[Dict[str, Any]],
    ) -> float:
        """Score 0-1 based on evidence richness."""
        score = 0.3  # base
        if issue_type != "general":
            score += 0.2
        score += min(len(evidence) * 0.05, 0.3)
        score += min(len(campaigns) * 0.1, 0.2)
        return min(score, 1.0)
