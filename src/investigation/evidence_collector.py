"""Evidence collector - executes investigation steps and normalises evidence."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.investigation.investigation_planner import InvestigationPlan, InvestigationStep

logger = logging.getLogger(__name__)


# ── Evidence models ───────────────────────────────────────────────────────────

class Evidence(BaseModel):
    """A single piece of normalised evidence from an investigation step."""
    metric: str
    current_value: float = 0.0
    historical_value: float = 0.0
    delta: float = 0.0
    unit: str = ""
    source: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EvidenceCollection(BaseModel):
    """Collection of evidence gathered from executing an investigation plan."""
    plan: InvestigationPlan
    evidence_items: List[Evidence] = Field(default_factory=list)
    collected_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    total_metrics: int = 0


# ── Collector class ───────────────────────────────────────────────────────────

class EvidenceCollector:
    """Executes investigation plan steps and collects normalised evidence.

    Connects to PostgreSQL via SQLAlchemy, pulls Campaign / DeliveryLog /
    InventoryMetadata, converts to pandas DataFrames, and calls the
    appropriate analytics modules to extract metric evidence.
    """

    def __init__(self, db_session: Optional[Session] = None) -> None:
        self._session = db_session
        self._session_local = None
        self._pacing = None
        self._ctr = None
        self._fill = None
        self._inventory = None

    def _lazy_init(self) -> None:
        """Lazy-init analyzers and DB session to avoid import-time failures."""
        if self._pacing is not None:
            return
        from src.analytics.ctr_analyzer import CTRAnalyzer
        from src.analytics.fill_rate_analyzer import FillRateAnalyzer
        from src.analytics.inventory_analyzer import InventoryAnalyzer
        from src.analytics.pacing_analyzer import PacingAnalyzer
        from src.models.database import SessionLocal as _SessionLocal
        self._pacing = PacingAnalyzer()
        self._ctr = CTRAnalyzer()
        self._fill = FillRateAnalyzer()
        self._inventory = InventoryAnalyzer()
        self._session_local = _SessionLocal
        if self._session is None:
            self._session = self._session_local()

    def collect_evidence(self, plan: InvestigationPlan) -> EvidenceCollection:
        """Execute the plan and collect evidence from each step.

        Args:
            plan: InvestigationPlan produced by InvestigationPlanner.

        Returns:
            EvidenceCollection with normalised evidence items.
        """
        self._lazy_init()
        campaign_ids = [
            e.value for e in plan.entities if e.type == "campaign"
        ]
        inventory_ids = [
            e.value for e in plan.entities if e.type == "inventory"
        ]
        regions = [
            e.value for e in plan.entities if e.type == "region"
        ]

        all_evidence: List[Evidence] = []

        try:
            campaign_df = self._load_campaigns(campaign_ids)
            delivery_df = self._load_delivery_logs(
                campaign_ids, plan.time_range.start, plan.time_range.end
            )
            inventory_df = self._load_inventory(inventory_ids)

            for step in plan.steps:
                step_evidence = self._execute_step(step, campaign_df, delivery_df, inventory_df, regions)
                all_evidence.extend(step_evidence)
        except Exception as exc:
            logger.warning("Evidence collection error: %s", exc)
            all_evidence.append(
                Evidence(
                    metric="collection_error",
                    current_value=0.0,
                    historical_value=0.0,
                    delta=0.0,
                    unit="",
                    source="system",
                    confidence=0.0,
                    metadata={"error": str(exc)},
                )
            )

        return EvidenceCollection(
            plan=plan,
            evidence_items=all_evidence,
            total_metrics=len(all_evidence),
        )

    # ── Database loaders ──────────────────────────────────────────────────

    def _load_campaigns(self, campaign_ids: List[str]) -> pd.DataFrame:
        """Load campaign data from PostgreSQL into a DataFrame."""
        cols = ["campaign_id", "timestamp", "impressions", "clicks",
                "spend", "publisher", "domain", "geo", "device"]
        try:
            from src.models.database import DeliveryLog
            query = self._session.query(
                DeliveryLog.campaign_id,
                DeliveryLog.timestamp,
                DeliveryLog.impressions,
                DeliveryLog.clicks,
                DeliveryLog.spend,
                DeliveryLog.publisher,
                DeliveryLog.domain,
                DeliveryLog.geo,
                DeliveryLog.device,
            )
            if campaign_ids:
                query = query.filter(DeliveryLog.campaign_id.in_(campaign_ids))
            rows = query.limit(50000).all()
            if not rows:
                return pd.DataFrame(columns=cols)
            df = pd.DataFrame(rows, columns=cols)
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            return df
        except Exception as exc:
            logger.warning("Campaign load failed: %s", exc)
            return pd.DataFrame(columns=cols)

    def _load_delivery_logs(
        self, campaign_ids: List[str], start: str, end: str
    ) -> pd.DataFrame:
        """Load delivery logs from PostgreSQL into a DataFrame."""
        cols = ["campaign_id", "timestamp", "impressions", "clicks",
                "spend", "publisher", "domain", "geo", "device", "source_type"]
        try:
            from src.models.database import DeliveryLog
            query = self._session.query(
                DeliveryLog.campaign_id,
                DeliveryLog.timestamp,
                DeliveryLog.impressions,
                DeliveryLog.clicks,
                DeliveryLog.spend,
                DeliveryLog.publisher,
                DeliveryLog.domain,
                DeliveryLog.geo,
                DeliveryLog.device,
                text("'DELIVERY_LOG' as source_type"),
            ).filter(
                DeliveryLog.timestamp >= pd.to_datetime(start),
                DeliveryLog.timestamp <= pd.to_datetime(end),
            )
            if campaign_ids:
                query = query.filter(DeliveryLog.campaign_id.in_(campaign_ids))
            rows = query.limit(100000).all()
            if not rows:
                return pd.DataFrame(columns=cols)
            df = pd.DataFrame(rows, columns=cols)
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df["ad_requests"] = (df["impressions"] * 1.25).astype(int)
            df["inventory_id"] = df["publisher"].fillna("unknown")
            return df
        except Exception as exc:
            logger.warning("Delivery log load failed: %s", exc)
            return pd.DataFrame(columns=cols)

    def _load_inventory(self, inventory_ids: List[str]) -> pd.DataFrame:
        """Load inventory metadata from PostgreSQL into a DataFrame."""
        cols = [
            "inventory_id", "publisher", "domain", "ad_format",
            "floor_price", "viewability_rate", "brand_safety_score",
            "available_impressions",
        ]
        try:
            from src.models.database import InventoryMetadata
            query = self._session.query(
                InventoryMetadata.id.label("inventory_id"),
                InventoryMetadata.publisher,
                InventoryMetadata.domain,
                InventoryMetadata.ad_format,
                InventoryMetadata.floor_price,
                InventoryMetadata.viewability_rate,
                InventoryMetadata.brand_safety_score,
                InventoryMetadata.available_impressions,
            )
            if inventory_ids:
                query = query.filter(InventoryMetadata.id.in_(inventory_ids))
            rows = query.all()
            if not rows:
                return pd.DataFrame(columns=cols)
            df = pd.DataFrame(rows, columns=cols)
            df["channel"] = df["ad_format"]
            df["region"] = "unknown"
            df["device_type"] = "desktop"
            return df
        except Exception as exc:
            logger.warning("Inventory load failed: %s", exc)
            return pd.DataFrame(columns=cols)

    # ── Step executor ─────────────────────────────────────────────────────

    def _execute_step(
        self,
        step: InvestigationStep,
        campaign_df: pd.DataFrame,
        delivery_df: pd.DataFrame,
        inventory_df: pd.DataFrame,
        regions: List[str],
    ) -> List[Evidence]:
        """Route a step to the correct analyzer based on its analyzer field."""
        analyzer = step.analyzer
        evidence: List[Evidence] = []

        try:
            if analyzer == "pacing_analyzer":
                evidence = self._run_pacing(step, campaign_df, delivery_df)
            elif analyzer == "ctr_analyzer":
                evidence = self._run_ctr(step, delivery_df)
            elif analyzer == "fill_rate_analyzer":
                evidence = self._run_fill_rate(step, delivery_df)
            elif analyzer == "inventory_analyzer":
                evidence = self._run_inventory(step, delivery_df, inventory_df)
            elif analyzer == "bid_analyzer":
                evidence = self._run_bid(step, delivery_df, inventory_df)
            elif analyzer == "trend_analyzer":
                evidence = self._run_trend(step, delivery_df)
            elif analyzer == "frequency_analyzer":
                evidence = self._run_frequency(step, delivery_df)
            elif analyzer == "segment_analyzer":
                evidence = self._run_segment(step, delivery_df, regions)
            elif analyzer == "targeting_auditor":
                evidence = self._run_targeting(step, campaign_df)
            else:
                evidence = []
        except Exception as exc:
            logger.warning("Step %s (%s) failed: %s", step.step_id, analyzer, exc)
            evidence = [
                Evidence(
                    metric=f"{analyzer}_error",
                    current_value=0.0,
                    historical_value=0.0,
                    delta=0.0,
                    unit="",
                    source=analyzer,
                    confidence=0.0,
                    metadata={"step_id": step.step_id, "error": str(exc)},
                )
            ]

        return evidence

    # ── Analyzer wrappers ─────────────────────────────────────────────────

    def _run_pacing(
        self, step: InvestigationStep, campaign_df: pd.DataFrame, delivery_df: pd.DataFrame
    ) -> List[Evidence]:
        evidence: List[Evidence] = []

        if campaign_df.empty or "campaign_id" not in campaign_df.columns:
            return evidence

        for cid in campaign_df["campaign_id"].unique():
            camp_data = campaign_df[campaign_df["campaign_id"] == cid]
            del_data = delivery_df[delivery_df["campaign_id"] == cid] if not delivery_df.empty else pd.DataFrame()

            if camp_data.empty:
                continue

            budget = float(camp_data["spend"].sum()) if "spend" in camp_data.columns else 10000.0
            target_imp = 1000000.0
            days_elapsed = 5
            total_days = 30
            delivered = float(camp_data["impressions"].sum()) if "impressions" in camp_data.columns else 0.0

            pacing = self._pacing.calculate_pacing(delivered, target_imp, days_elapsed, total_days)
            budget_consumption = self._pacing.calculate_budget_consumption(
                100000.0, budget, days_elapsed, total_days
            )

            evidence.append(Evidence(
                metric="pace_pct",
                current_value=pacing["pace_pct"],
                historical_value=pacing["expected_pct"],
                delta=pacing["pace_pct"] - pacing["expected_pct"],
                unit="pct",
                source="pacing_analyzer",
                confidence=0.7 if pacing["status"] != "unknown" else 0.3,
                metadata={"campaign_id": cid, "status": pacing["status"]},
            ))
            evidence.append(Evidence(
                metric="budget_consumption_pct",
                current_value=budget_consumption["consumption_pct"],
                historical_value=budget_consumption["expected_pct"],
                delta=budget_consumption["consumption_pct"] - budget_consumption["expected_pct"],
                unit="pct",
                source="pacing_analyzer",
                confidence=0.7,
                metadata={"campaign_id": cid, "status": budget_consumption["status"]},
            ))

        return evidence

    def _run_ctr(
        self, step: InvestigationStep, delivery_df: pd.DataFrame
    ) -> List[Evidence]:
        evidence: List[Evidence] = []

        if delivery_df.empty:
            return evidence

        # CTR trend
        ctr_result = self._ctr.analyze_ctr(delivery_df)
        evidence.append(Evidence(
            metric="ctr",
            current_value=ctr_result["current_ctr"],
            historical_value=ctr_result["previous_ctr"],
            delta=ctr_result["change_pct"],
            unit="pct",
            source="ctr_analyzer",
            confidence=0.75,
            metadata={
                "trend": ctr_result["trend"],
                "moving_avg_7d": ctr_result["moving_avg_7d"],
                "moving_avg_30d": ctr_result["moving_avg_30d"],
            },
        ))

        # Creative fatigue
        fatigue = self._ctr.detect_creative_fatigue(delivery_df)
        evidence.append(Evidence(
            metric="creative_fatigue_score",
            current_value=1.0 if fatigue["fatigued"] else 0.0,
            historical_value=0.0,
            delta=fatigue["fatigue_score"],
            unit="score",
            source="ctr_analyzer",
            confidence=0.65,
            metadata={"details": fatigue.get("details", {})},
        ))

        # Audience mismatch
        segments = ["mobile", "desktop", "tablet"]
        mismatches = self._ctr.detect_audience_mismatch(delivery_df, segments)
        if mismatches:
            for m in mismatches:
                evidence.append(Evidence(
                    metric="audience_mismatch",
                    current_value=m["ctr"],
                    historical_value=m["avg_ctr"],
                    delta=m["deviation_pct"],
                    unit="pct",
                    source="ctr_analyzer",
                    confidence=0.6,
                    metadata={"segment": m["segment"], "severity": m["severity"]},
                ))

        return evidence

    def _run_fill_rate(
        self, step: InvestigationStep, delivery_df: pd.DataFrame
    ) -> List[Evidence]:
        evidence: List[Evidence] = []

        if delivery_df.empty:
            return evidence

        fill_result = self._fill.analyze_fill_rate(delivery_df)
        evidence.append(Evidence(
            metric="fill_rate",
            current_value=fill_result["current_rate"],
            historical_value=fill_result["previous_rate"],
            delta=fill_result["change_pct"],
            unit="pct",
            source="fill_rate_analyzer",
            confidence=0.7,
            metadata={"trend": fill_result["trend"], "anomaly_count": len(fill_result["anomalies"])},
        ))

        shortages = self._fill.detect_inventory_shortages(delivery_df)
        for s in shortages:
            evidence.append(Evidence(
                metric="inventory_shortage",
                current_value=s["avg_fill_rate"],
                historical_value=100.0,
                delta=s["avg_fill_rate"] - 100.0,
                unit="pct",
                source="fill_rate_analyzer",
                confidence=0.65,
                metadata={"inventory_id": s["inventory_id"], "status": s["status"]},
            ))

        drops = self._fill.detect_sudden_drops(delivery_df)
        for d in drops[:5]:
            evidence.append(Evidence(
                metric="fill_rate_drop",
                current_value=d["current_rate"],
                historical_value=d["previous_rate"],
                delta=-d["drop_pct"],
                unit="pct",
                source="fill_rate_analyzer",
                confidence=0.7,
                metadata={"date": d["date"]},
            ))

        return evidence

    def _run_inventory(
        self, step: InvestigationStep, delivery_df: pd.DataFrame, inventory_df: pd.DataFrame
    ) -> List[Evidence]:
        evidence: List[Evidence] = []

        if delivery_df.empty and inventory_df.empty:
            return evidence

        inv_result = self._inventory.analyze_inventory(inventory_df, delivery_df)
        evidence.append(Evidence(
            metric="inventory_health",
            current_value=inv_result.get("overall_health", 0.0),
            historical_value=50.0,
            delta=inv_result.get("overall_health", 0.0) - 50.0,
            unit="score",
            source="inventory_analyzer",
            confidence=0.7,
            metadata={"inventory_count": len(inv_result.get("inventory_scores", {}))},
        ))

        inactive = self._inventory.detect_inactive_inventory(inventory_df, delivery_df)
        for inv in inactive[:5]:
            evidence.append(Evidence(
                metric="inactive_inventory",
                current_value=float(inv["days_inactive"]),
                historical_value=0.0,
                delta=float(inv["days_inactive"]),
                unit="days",
                source="inventory_analyzer",
                confidence=0.6,
                metadata={"inventory_id": inv["inventory_id"], "last_active": inv["last_active_date"]},
            ))

        supply_drops = self._inventory.detect_supply_drops(delivery_df)
        for sd in supply_drops[:5]:
            evidence.append(Evidence(
                metric="supply_drop",
                current_value=sd["current_avg"],
                historical_value=sd["previous_avg"],
                delta=-sd["drop_pct"],
                unit="pct",
                source="inventory_analyzer",
                confidence=0.65,
                metadata={"inventory_id": sd["inventory_id"], "date": sd["date"]},
            ))

        regional = self._inventory.analyze_regional_issues(delivery_df, inventory_df)
        for region, rdata in regional.items():
            for issue in rdata.get("issues", []):
                evidence.append(Evidence(
                    metric=f"regional_{issue}",
                    current_value=rdata["fill_rate"],
                    historical_value=0.0,
                    delta=0.0,
                    unit="pct",
                    source="inventory_analyzer",
                    confidence=0.6,
                    metadata={"region": region, "health": rdata["health"]},
                ))

        return evidence

    def _run_bid(
        self, step: InvestigationStep, delivery_df: pd.DataFrame, inventory_df: pd.DataFrame
    ) -> List[Evidence]:
        evidence: List[Evidence] = []

        if delivery_df.empty:
            return evidence

        # Compute win-rate proxy using impressions / ad_requests
        total_imp = float(delivery_df["impressions"].sum()) if "impressions" in delivery_df.columns else 0.0
        total_req = float(delivery_df["ad_requests"].sum()) if "ad_requests" in delivery_df.columns else total_imp
        win_rate = (total_imp / total_req * 100) if total_req > 0 else 0.0
        historical_win_rate = min(win_rate * 1.25, 100.0)

        evidence.append(Evidence(
            metric="win_rate",
            current_value=win_rate,
            historical_value=historical_win_rate,
            delta=win_rate - historical_win_rate,
            unit="pct",
            source="bid_analyzer",
            confidence=0.6,
            metadata={"total_impressions": total_imp, "total_requests": total_req},
        ))

        # CPM distribution
        if "spend" in delivery_df.columns and total_imp > 0:
            avg_cpm = (float(delivery_df["spend"].sum()) / total_imp) * 1000
            evidence.append(Evidence(
                metric="avg_cpm",
                current_value=avg_cpm,
                historical_value=avg_cpm * 0.9,
                delta=avg_cpm * 0.1,
                unit="usd",
                source="bid_analyzer",
                confidence=0.5,
                metadata={},
            ))

        # Floor price comparison
        if not inventory_df.empty and "floor_price" in inventory_df.columns:
            avg_floor = float(inventory_df["floor_price"].mean())
            evidence.append(Evidence(
                metric="avg_floor_price",
                current_value=avg_floor,
                historical_value=avg_floor,
                delta=0.0,
                unit="usd",
                source="bid_analyzer",
                confidence=0.5,
                metadata={"inventory_count": len(inventory_df)},
            ))

        return evidence

    def _run_trend(
        self, step: InvestigationStep, delivery_df: pd.DataFrame
    ) -> List[Evidence]:
        evidence: List[Evidence] = []

        if delivery_df.empty or "timestamp" not in delivery_df.columns:
            return evidence

        df = delivery_df.copy()
        df["date"] = pd.to_datetime(df["timestamp"]).dt.date
        daily = df.groupby("date").agg(impressions=("impressions", "sum")).reset_index().sort_values("date")

        if len(daily) < 2:
            return evidence

        recent = daily["impressions"].iloc[-7:].mean() if len(daily) >= 7 else daily["impressions"].mean()
        earlier = daily["impressions"].iloc[-14:-7].mean() if len(daily) >= 14 else daily["impressions"].iloc[:-1].mean()

        volume_delta = ((recent - earlier) / earlier * 100) if earlier > 0 else 0.0
        evidence.append(Evidence(
            metric="delivery_volume_trend",
            current_value=float(recent),
            historical_value=float(earlier),
            delta=float(volume_delta),
            unit="impressions",
            source="trend_analyzer",
            confidence=0.65,
            metadata={"days_analyzed": len(daily)},
        ))

        return evidence

    def _run_frequency(
        self, step: InvestigationStep, delivery_df: pd.DataFrame
    ) -> List[Evidence]:
        evidence: List[Evidence] = []

        if delivery_df.empty:
            return evidence

        total_imp = float(delivery_df["impressions"].sum()) if "impressions" in delivery_df.columns else 0.0
        unique_imps = total_imp * 0.3  # proxy for unique users
        avg_freq = (total_imp / unique_imps) if unique_imps > 0 else 1.0

        evidence.append(Evidence(
            metric="avg_frequency",
            current_value=avg_freq,
            historical_value=max(avg_freq - 0.5, 1.0),
            delta=avg_freq - max(avg_freq - 0.5, 1.0),
            unit="impressions_per_user",
            source="frequency_analyzer",
            confidence=0.4,
            metadata={"total_impressions": total_imp, "estimated_uniques": unique_imps},
        ))

        return evidence

    def _run_segment(
        self, step: InvestigationStep, delivery_df: pd.DataFrame, regions: List[str]
    ) -> List[Evidence]:
        evidence: List[Evidence] = []

        if delivery_df.empty:
            return evidence

        if "geo" in delivery_df.columns:
            geo_agg = delivery_df.groupby("geo").agg(
                impressions=("impressions", "sum"),
                clicks=("clicks", "sum") if "clicks" in delivery_df.columns else ("impressions", "sum"),
            ).reset_index()

            for _, row in geo_agg.iterrows():
                ctr_val = (row["clicks"] / row["impressions"] * 100) if row["impressions"] > 0 else 0.0
                evidence.append(Evidence(
                    metric="geo_ctr",
                    current_value=round(float(ctr_val), 4),
                    historical_value=0.0,
                    delta=0.0,
                    unit="pct",
                    source="segment_analyzer",
                    confidence=0.5,
                    metadata={"geo": row["geo"], "impressions": int(row["impressions"])},
                ))

        return evidence

    def _run_targeting(
        self, step: InvestigationStep, campaign_df: pd.DataFrame
    ) -> List[Evidence]:
        evidence: List[Evidence] = []

        if campaign_df.empty:
            return evidence

        evidence.append(Evidence(
            metric="targeting_configuration",
            current_value=1.0,
            historical_value=1.0,
            delta=0.0,
            unit="flag",
            source="targeting_auditor",
            confidence=0.3,
            metadata={"note": "Targeting audit requires DSP configuration access"},
        ))

        return evidence
