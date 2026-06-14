"""CTR analysis for ad creative performance and audience diagnostics."""

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


class CTRAnalyzer:
    """Analyzes click-through rates, detects creative fatigue, and audits audience fit."""

    @staticmethod
    def calculate_ctr(clicks: float, impressions: float) -> float:
        """Calculate CTR as a percentage.

        Args:
            clicks: Number of clicks.
            impressions: Number of impressions.

        Returns:
            CTR as a percentage (0-100). Returns 0.0 if impressions is zero.
        """
        if impressions <= 0:
            return 0.0
        return round((clicks / impressions) * 100, 4)

    def analyze_ctr(
        self,
        delivery_df: pd.DataFrame,
        campaign_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analyze CTR trends with moving averages and diagnostics.

        Expects delivery_df with columns:
            timestamp (datetime), clicks (int), impressions (int), campaign_id (str),
            creative_id (str), segment (str), inventory_id (str)

        Args:
            delivery_df: DataFrame with delivery metrics.
            campaign_id: Optional campaign filter.

        Returns:
            Dict with current_ctr, previous_ctr, change_pct, trend, moving_avg_7d,
            moving_avg_30d, diagnostics.
        """
        df = delivery_df.copy()

        if campaign_id is not None:
            df = df[df["campaign_id"] == campaign_id]

        if df.empty:
            return self._empty_ctr_result()

        df = df.sort_values("timestamp").copy()
        df["date"] = pd.to_datetime(df["timestamp"]).dt.date

        daily = df.groupby("date").agg(
            clicks=("clicks", "sum"),
            impressions=("impressions", "sum"),
        ).reset_index()

        daily["ctr"] = daily.apply(
            lambda row: self.calculate_ctr(row["clicks"], row["impressions"]),
            axis=1,
        )

        daily = daily.sort_values("date").reset_index(drop=True)
        ctr_values = daily["ctr"].values

        if len(ctr_values) == 0:
            return self._empty_ctr_result()

        current_ctr = float(ctr_values[-1])
        previous_ctr = float(ctr_values[-2]) if len(ctr_values) >= 2 else current_ctr

        change_pct = 0.0
        if previous_ctr != 0:
            change_pct = round(((current_ctr - previous_ctr) / previous_ctr) * 100, 4)

        if len(ctr_values) >= 7:
            ma_7 = float(np.mean(ctr_values[-7:]))
        else:
            ma_7 = float(np.mean(ctr_values))

        if len(ctr_values) >= 30:
            ma_30 = float(np.mean(ctr_values[-30:]))
        else:
            ma_30 = float(np.mean(ctr_values))

        mean_ctr = float(np.mean(ctr_values))
        std_ctr = float(np.std(ctr_values)) if len(ctr_values) > 1 else 0.0

        if std_ctr > 0:
            z_current = (current_ctr - mean_ctr) / std_ctr
        else:
            z_current = 0.0

        if change_pct > 5 and z_current > 1.0:
            trend = "improving"
        elif change_pct < -5 and z_current < -1.0:
            trend = "declining"
        elif abs(change_pct) < 2:
            trend = "stable"
        else:
            trend = "volatile"

        diagnostics = self._compute_diagnostics(df, daily)

        return {
            "current_ctr": round(current_ctr, 4),
            "previous_ctr": round(previous_ctr, 4),
            "change_pct": round(change_pct, 4),
            "trend": trend,
            "moving_avg_7d": round(ma_7, 4),
            "moving_avg_30d": round(ma_30, 4),
            "diagnostics": diagnostics,
        }

    def _empty_ctr_result(self) -> Dict[str, Any]:
        return {
            "current_ctr": 0.0,
            "previous_ctr": 0.0,
            "change_pct": 0.0,
            "trend": "stable",
            "moving_avg_7d": 0.0,
            "moving_avg_30d": 0.0,
            "diagnostics": {},
        }

    def _compute_diagnostics(
        self, raw_df: pd.DataFrame, daily_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Compute detailed diagnostics from raw and daily data."""
        diag: Dict[str, Any] = {}

        ctr_values = daily_df["ctr"].values.astype(float)
        if len(ctr_values) > 1:
            diag["volatility"] = round(float(np.std(ctr_values)), 4)
            diag["mean"] = round(float(np.mean(ctr_values)), 4)
            diag["min"] = round(float(np.min(ctr_values)), 4)
            diag["max"] = round(float(np.max(ctr_values)), 4)
        else:
            diag["volatility"] = 0.0
            diag["mean"] = round(float(ctr_values[0]), 4) if len(ctr_values) == 1 else 0.0
            diag["min"] = diag["mean"]
            diag["max"] = diag["mean"]

        if "creative_id" in raw_df.columns and not raw_df.empty:
            creative_agg = (
                raw_df.groupby("creative_id")
                .agg(clicks=("clicks", "sum"), impressions=("impressions", "sum"))
                .reset_index()
            )
            creative_agg["ctr"] = creative_agg.apply(
                lambda row: self.calculate_ctr(row["clicks"], row["impressions"]),
                axis=1,
            )
            best_idx = creative_agg["ctr"].idxmax()
            worst_idx = creative_agg["ctr"].idxmin()
            diag["best_creative"] = {
                "creative_id": creative_agg.loc[best_idx, "creative_id"],
                "ctr": round(float(creative_agg.loc[best_idx, "ctr"]), 4),
            }
            diag["worst_creative"] = {
                "creative_id": creative_agg.loc[worst_idx, "creative_id"],
                "ctr": round(float(creative_agg.loc[worst_idx, "ctr"]), 4),
            }

        if "segment" in raw_df.columns and not raw_df.empty:
            segment_agg = (
                raw_df.groupby("segment")
                .agg(clicks=("clicks", "sum"), impressions=("impressions", "sum"))
                .reset_index()
            )
            segment_agg["ctr"] = segment_agg.apply(
                lambda row: self.calculate_ctr(row["clicks"], row["impressions"]),
                axis=1,
            )
            diag["segment_breakdown"] = {
                row["segment"]: round(float(row["ctr"]), 4)
                for _, row in segment_agg.iterrows()
            }

        return diag

    def detect_creative_fatigue(
        self,
        df: pd.DataFrame,
        window: int = 7,
    ) -> Dict[str, Any]:
        """Detect creative fatigue via declining CTR over a rolling window.

        Fatigue is flagged when the recent window CTR is significantly lower
        than the earlier window CTR.

        Args:
            df: DataFrame with timestamp, clicks, impressions, creative_id.
            window: Rolling window size in days.

        Returns:
            Dict with fatigued (bool), fatigue_score (0-1), and details.
        """
        if df.empty:
            return {"fatigued": False, "fatigue_score": 0.0, "details": {}}

        working = df.copy()
        working["date"] = pd.to_datetime(working["timestamp"]).dt.date

        daily = (
            working.groupby("date")
            .agg(clicks=("clicks", "sum"), impressions=("impressions", "sum"))
            .reset_index()
            .sort_values("date")
        )

        daily["ctr"] = daily.apply(
            lambda row: self.calculate_ctr(row["clicks"], row["impressions"]),
            axis=1,
        )

        ctr_vals = daily["ctr"].values.astype(float)

        if len(ctr_vals) < window * 2:
            return {
                "fatigued": False,
                "fatigue_score": 0.0,
                "details": {"reason": "insufficient_data"},
            }

        recent = ctr_vals[-window:]
        earlier = ctr_vals[-window * 2 : -window]

        recent_mean = float(np.mean(recent))
        earlier_mean = float(np.mean(earlier))

        if earlier_mean == 0:
            fatigue_ratio = 0.0
        else:
            fatigue_ratio = (earlier_mean - recent_mean) / earlier_mean

        fatigue_score = float(np.clip(fatigue_ratio, 0.0, 1.0))
        fatigued = fatigue_score > 0.15

        return {
            "fatigued": fatigued,
            "fatigue_score": round(fatigue_score, 4),
            "details": {
                "recent_window_avg": round(recent_mean, 4),
                "earlier_window_avg": round(earlier_mean, 4),
                "decline_pct": round(fatigue_ratio * 100, 2),
                "window_size": window,
            },
        }

    def detect_audience_mismatch(
        self, df: pd.DataFrame, segments: List[str]
    ) -> List[Dict[str, Any]]:
        """Identify audience segments with significantly lower CTR than average.

        Args:
            df: DataFrame with timestamp, clicks, impressions, segment.
            segments: List of segment column values to evaluate.

        Returns:
            List of dicts with segment, ctr, avg_ctr, deviation_pct, severity.
        """
        if df.empty or "segment" not in df.columns:
            return []

        agg = (
            df.groupby("segment")
            .agg(clicks=("clicks", "sum"), impressions=("impressions", "sum"))
            .reset_index()
        )

        agg["ctr"] = agg.apply(
            lambda row: self.calculate_ctr(row["clicks"], row["impressions"]),
            axis=1,
        )

        overall_mean = float(np.mean(agg["ctr"].values))

        target_agg = agg[agg["segment"].isin(segments)]

        mismatches: List[Dict[str, Any]] = []
        for _, row in target_agg.iterrows():
            ctr_val = float(row["ctr"])
            if overall_mean > 0:
                deviation = ((ctr_val - overall_mean) / overall_mean) * 100
            else:
                deviation = 0.0

            if deviation < -30:
                severity = "high"
            elif deviation < -15:
                severity = "medium"
            elif deviation < -5:
                severity = "low"
            else:
                severity = "none"

            if severity != "none":
                mismatches.append(
                    {
                        "segment": row["segment"],
                        "ctr": round(ctr_val, 4),
                        "avg_ctr": round(overall_mean, 4),
                        "deviation_pct": round(deviation, 2),
                        "severity": severity,
                    }
                )

        mismatches.sort(key=lambda x: x["deviation_pct"])
        return mismatches

    def assess_inventory_quality(
        self, df: pd.DataFrame, inventory_df: pd.DataFrame
    ) -> Dict[str, Dict[str, Any]]:
        """Assess quality scores per inventory source based on CTR and engagement.

        Args:
            df: Delivery DataFrame with inventory_id, clicks, impressions.
            inventory_df: Inventory metadata DataFrame with inventory_id and optional
                domain, channel, device_type columns.

        Returns:
            Dict keyed by inventory_id with quality_score (0-100), ctr, and metadata.
        """
        if df.empty or "inventory_id" not in df.columns:
            return {}

        agg = (
            df.groupby("inventory_id")
            .agg(clicks=("clicks", "sum"), impressions=("impressions", "sum"))
            .reset_index()
        )

        agg["ctr"] = agg.apply(
            lambda row: self.calculate_ctr(row["clicks"], row["impressions"]),
            axis=1,
        )

        ctr_values = agg["ctr"].values.astype(float)
        if len(ctr_values) == 0:
            return {}

        mean_ctr = float(np.mean(ctr_values))
        std_ctr = float(np.std(ctr_values)) if len(ctr_values) > 1 else 1.0

        inv_meta = {}
        if not inventory_df.empty and "inventory_id" in inventory_df.columns:
            for _, row in inventory_df.iterrows():
                meta: Dict[str, Any] = {}
                for col in inventory_df.columns:
                    if col != "inventory_id":
                        meta[col] = row[col]
                inv_meta[row["inventory_id"]] = meta

        scores: Dict[str, Dict[str, Any]] = {}
        for _, row in agg.iterrows():
            inv_id = row["inventory_id"]
            ctr_val = float(row["ctr"])

            if std_ctr > 0:
                z = (ctr_val - mean_ctr) / std_ctr
            else:
                z = 0.0

            quality_score = float(np.clip(50 + (z * 20), 0, 100))

            scores[inv_id] = {
                "quality_score": round(quality_score, 2),
                "ctr": round(ctr_val, 4),
                "impressions": int(row["impressions"]),
                "clicks": int(row["clicks"]),
                "metadata": inv_meta.get(inv_id, {}),
            }

        return scores
