"""Inventory health analysis for supply monitoring and issue detection."""

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


class InventoryAnalyzer:
    """Monitors inventory health, detects supply drops, and identifies regional issues."""

    def analyze_inventory(
        self,
        inventory_df: pd.DataFrame,
        delivery_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """Compute overall inventory health scores and aggregate statistics.

        inventory_df columns: inventory_id, domain, channel, region, device_type
        delivery_df columns: inventory_id, timestamp, impressions, ad_requests, clicks

        Args:
            inventory_df: Inventory metadata.
            delivery_df: Delivery performance data.

        Returns:
            Dict with overall_health, per_inventory scores, and aggregate stats.
        """
        if inventory_df.empty or delivery_df.empty:
            return {"overall_health": 0.0, "inventory_scores": {}, "aggregates": {}}

        delivery_agg = (
            delivery_df.groupby("inventory_id")
            .agg(
                impressions=("impressions", "sum"),
                ad_requests=("ad_requests", "sum"),
                clicks=("clicks", "sum") if "clicks" in delivery_df.columns else ("impressions", "sum"),
            )
            .reset_index()
        )

        delivery_agg["fill_rate"] = delivery_agg.apply(
            lambda row: (row["impressions"] / row["ad_requests"] * 100)
            if row["ad_requests"] > 0
            else 0.0,
            axis=1,
        )

        delivery_agg["ctr"] = delivery_agg.apply(
            lambda row: (row["clicks"] / row["impressions"] * 100)
            if row["impressions"] > 0
            else 0.0,
            axis=1,
        )

        inv_scores: Dict[str, Dict[str, Any]] = {}
        for _, row in delivery_agg.iterrows():
            inv_id = row["inventory_id"]
            metrics = {
                "fill_rate": row["fill_rate"],
                "ctr": row["ctr"],
                "impressions": int(row["impressions"]),
                "ad_requests": int(row["ad_requests"]),
            }
            score = self.get_inventory_health_score(inv_id, metrics)
            inv_scores[inv_id] = {
                "health_score": score,
                "fill_rate": round(float(row["fill_rate"]), 4),
                "ctr": round(float(row["ctr"]), 4),
                "impressions": int(row["impressions"]),
            }

        overall_health = (
            float(np.mean([s["health_score"] for s in inv_scores.values()]))
            if inv_scores
            else 0.0
        )

        aggregates = self._compute_aggregates(inventory_df, delivery_df)

        return {
            "overall_health": round(overall_health, 2),
            "inventory_scores": inv_scores,
            "aggregates": aggregates,
        }

    def detect_inactive_inventory(
        self,
        inventory_df: pd.DataFrame,
        delivery_df: pd.DataFrame,
        lookback_days: int = 7,
    ) -> List[Dict[str, Any]]:
        """Find inventory sources with no impressions in the lookback window.

        Args:
            inventory_df: Inventory metadata.
            delivery_df: Delivery data with timestamp and inventory_id.
            lookback_days: Number of recent days to check.

        Returns:
            List of dicts with inventory_id, last_active_date, days_inactive.
        """
        if inventory_df.empty or delivery_df.empty:
            return []

        working = delivery_df.copy()
        working["timestamp"] = pd.to_datetime(working["timestamp"])

        cutoff = working["timestamp"].max() - pd.Timedelta(days=lookback_days)

        recent = working[working["timestamp"] >= cutoff]

        active_ids = set(recent["inventory_id"].unique()) if not recent.empty else set()
        all_ids = set(inventory_df["inventory_id"].unique())

        inactive_ids = all_ids - active_ids

        results: List[Dict[str, Any]] = []
        for inv_id in inactive_ids:
            inv_data = working[working["inventory_id"] == inv_id]
            if inv_data.empty:
                last_active = None
                days_inactive = lookback_days
            else:
                last_active = inv_data["timestamp"].max()
                days_inactive = (working["timestamp"].max() - last_active).days

            results.append(
                {
                    "inventory_id": inv_id,
                    "last_active_date": str(last_active.date()) if last_active is not None else None,
                    "days_inactive": days_inactive,
                }
            )

        results.sort(key=lambda x: x["days_inactive"], reverse=True)
        return results

    def detect_supply_drops(
        self,
        delivery_df: pd.DataFrame,
        window: int = 7,
        threshold: float = 0.2,
    ) -> List[Dict[str, Any]]:
        """Detect inventory sources with significant drops in daily impressions.

        Uses rolling window comparison to identify supply contractions.

        Args:
            delivery_df: Delivery data with timestamp, inventory_id, impressions.
            window: Rolling window size in days.
            threshold: Minimum percentage drop to flag (0.2 = 20%).

        Returns:
            List of dicts with inventory_id, date, current_avg, previous_avg, drop_pct.
        """
        if delivery_df.empty:
            return []

        working = delivery_df.copy()
        working["date"] = pd.to_datetime(working["timestamp"]).dt.date

        daily = (
            working.groupby(["date", "inventory_id"])
            .agg(impressions=("impressions", "sum"))
            .reset_index()
            .sort_values("date")
        )

        drops: List[Dict[str, Any]] = []

        for inv_id, group in daily.groupby("inventory_id"):
            if len(group) < window * 2:
                continue

            group = group.sort_values("date").reset_index(drop=True)
            impressions = group["impressions"].values.astype(float)
            dates = group["date"].values

            for i in range(window * 2, len(impressions)):
                recent_window = impressions[i - window : i]
                earlier_window = impressions[i - window * 2 : i - window]

                recent_avg = float(np.mean(recent_window))
                earlier_avg = float(np.mean(earlier_window))

                if earlier_avg > 0:
                    drop_pct = (earlier_avg - recent_avg) / earlier_avg
                else:
                    drop_pct = 0.0

                if drop_pct >= threshold:
                    drops.append(
                        {
                            "inventory_id": inv_id,
                            "date": str(dates[i]),
                            "current_avg": round(recent_avg, 2),
                            "previous_avg": round(earlier_avg, 2),
                            "drop_pct": round(drop_pct * 100, 2),
                        }
                    )

        drops.sort(key=lambda x: x["drop_pct"], reverse=True)
        return drops

    def analyze_regional_issues(
        self,
        delivery_df: pd.DataFrame,
        inventory_df: pd.DataFrame,
    ) -> Dict[str, Dict[str, Any]]:
        """Analyze delivery performance broken down by region.

        Args:
            delivery_df: Delivery data with inventory_id, impressions, ad_requests, clicks.
            inventory_df: Inventory metadata with inventory_id, region.

        Returns:
            Dict keyed by region with impressions, fill_rate, ctr, health assessment.
        """
        if delivery_df.empty or inventory_df.empty:
            return {}

        if "region" not in inventory_df.columns:
            return {}

        merged = delivery_df.merge(
            inventory_df[["inventory_id", "region"]], on="inventory_id", how="left"
        )

        merged = merged.dropna(subset=["region"])

        if merged.empty:
            return {}

        regional = (
            merged.groupby("region")
            .agg(
                impressions=("impressions", "sum"),
                ad_requests=("ad_requests", "sum"),
                clicks=("clicks", "sum") if "clicks" in merged.columns else ("impressions", "sum"),
            )
            .reset_index()
        )

        regional["fill_rate"] = regional.apply(
            lambda row: (row["impressions"] / row["ad_requests"] * 100)
            if row["ad_requests"] > 0
            else 0.0,
            axis=1,
        )

        regional["ctr"] = regional.apply(
            lambda row: (row["clicks"] / row["impressions"] * 100)
            if row["impressions"] > 0
            else 0.0,
            axis=1,
        )

        fill_mean = float(np.mean(regional["fill_rate"].values))
        fill_std = float(np.std(regional["fill_rate"].values)) if len(regional) > 1 else 1.0
        ctr_mean = float(np.mean(regional["ctr"].values))
        ctr_std = float(np.std(regional["ctr"].values)) if len(regional) > 1 else 1.0

        results: Dict[str, Dict[str, Any]] = {}
        for _, row in regional.iterrows():
            region = row["region"]
            fill_rate = float(row["fill_rate"])
            ctr = float(row["ctr"])

            if fill_std > 0:
                fill_z = (fill_rate - fill_mean) / fill_std
            else:
                fill_z = 0.0

            if ctr_std > 0:
                ctr_z = (ctr - ctr_mean) / ctr_std
            else:
                ctr_z = 0.0

            if fill_z < -1.5:
                health = "poor"
            elif fill_z < -0.5:
                health = "below_average"
            elif fill_z > 1.5:
                health = "excellent"
            else:
                health = "normal"

            issues = []
            if fill_z < -1.0:
                issues.append("low_fill_rate")
            if ctr_z < -1.0:
                issues.append("low_ctr")
            if fill_z < -2.0:
                issues.append("critical_fill_rate")

            results[region] = {
                "impressions": int(row["impressions"]),
                "fill_rate": round(fill_rate, 4),
                "ctr": round(ctr, 4),
                "health": health,
                "issues": issues,
                "fill_rate_z": round(fill_z, 4),
                "ctr_z": round(ctr_z, 4),
            }

        return results

    def get_inventory_health_score(
        self,
        inventory_id: str,
        metrics: Dict[str, float],
    ) -> float:
        """Calculate a 0-100 health score for a single inventory source.

        Scoring weights:
            - Fill rate: 40%
            - CTR: 30%
            - Volume consistency: 20%
            - Request fulfillment: 10%

        Args:
            inventory_id: The inventory source identifier.
            metrics: Dict with fill_rate, ctr, impressions, ad_requests.

        Returns:
            Health score between 0 and 100.
        """
        fill_rate = metrics.get("fill_rate", 0.0)
        ctr = metrics.get("ctr", 0.0)
        impressions = metrics.get("impressions", 0)
        ad_requests = metrics.get("ad_requests", 0)

        fill_score = min(fill_rate / 100 * 100, 100.0) if fill_rate <= 100 else min(fill_rate, 100.0)

        ctr_score = min(ctr / 5 * 100, 100.0) if ctr <= 5 else 100.0

        if ad_requests > 0:
            volume_ratio = impressions / ad_requests
            volume_score = min(volume_ratio * 100, 100.0)
        else:
            volume_score = 0.0

        fulfillment_score = min(
            (impressions / max(ad_requests, 1)) * 100, 100.0
        )

        health = (
            fill_score * 0.40
            + ctr_score * 0.30
            + volume_score * 0.20
            + fulfillment_score * 0.10
        )

        return round(float(np.clip(health, 0, 100)), 2)

    def _compute_aggregates(
        self,
        inventory_df: pd.DataFrame,
        delivery_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """Compute aggregate stats by channel, region, and device_type."""
        merged = delivery_df.merge(
            inventory_df[["inventory_id", "channel", "region", "device_type"]],
            on="inventory_id",
            how="left",
        )

        agg: Dict[str, Any] = {}

        if "channel" in merged.columns:
            channel_stats = (
                merged.groupby("channel")
                .agg(impressions=("impressions", "sum"), ad_requests=("ad_requests", "sum"))
                .reset_index()
            )
            channel_stats["fill_rate"] = channel_stats.apply(
                lambda row: (row["impressions"] / row["ad_requests"] * 100)
                if row["ad_requests"] > 0
                else 0.0,
                axis=1,
            )
            agg["by_channel"] = {
                row["channel"]: {
                    "impressions": int(row["impressions"]),
                    "fill_rate": round(float(row["fill_rate"]), 4),
                }
                for _, row in channel_stats.iterrows()
            }

        if "region" in merged.columns:
            region_stats = (
                merged.groupby("region")
                .agg(impressions=("impressions", "sum"), ad_requests=("ad_requests", "sum"))
                .reset_index()
            )
            region_stats["fill_rate"] = region_stats.apply(
                lambda row: (row["impressions"] / row["ad_requests"] * 100)
                if row["ad_requests"] > 0
                else 0.0,
                axis=1,
            )
            agg["by_region"] = {
                row["region"]: {
                    "impressions": int(row["impressions"]),
                    "fill_rate": round(float(row["fill_rate"]), 4),
                }
                for _, row in region_stats.iterrows()
            }

        if "device_type" in merged.columns:
            device_stats = (
                merged.groupby("device_type")
                .agg(impressions=("impressions", "sum"), ad_requests=("ad_requests", "sum"))
                .reset_index()
            )
            device_stats["fill_rate"] = device_stats.apply(
                lambda row: (row["impressions"] / row["ad_requests"] * 100)
                if row["ad_requests"] > 0
                else 0.0,
                axis=1,
            )
            agg["by_device"] = {
                row["device_type"]: {
                    "impressions": int(row["impressions"]),
                    "fill_rate": round(float(row["fill_rate"]), 4),
                }
                for _, row in device_stats.iterrows()
            }

        return agg
