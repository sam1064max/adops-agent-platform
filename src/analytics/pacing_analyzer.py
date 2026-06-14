"""Pacing analysis for campaign delivery tracking and budget management."""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


class PacingAnalyzer:
    """Tracks campaign pacing, detects delivery anomalies, and projects completion."""

    @staticmethod
    def calculate_pacing(
        delivered: float,
        target: float,
        days_elapsed: int,
        total_days: int,
    ) -> Dict[str, Any]:
        """Calculate pacing metrics for a campaign.

        Args:
            delivered: Units delivered so far (impressions, spend, etc.).
            target: Total target/goal.
            days_elapsed: Days since campaign start.
            total_days: Total planned campaign duration.

        Returns:
            Dict with pace_pct, daily_rate, projected_total, status.
        """
        if total_days <= 0 or target <= 0:
            return {
                "pace_pct": 0.0,
                "daily_rate": 0.0,
                "projected_total": 0.0,
                "status": "unknown",
            }

        expected_pct = (days_elapsed / total_days) * 100
        pace_pct = (delivered / target * 100) if target > 0 else 0.0

        daily_rate = delivered / days_elapsed if days_elapsed > 0 else 0.0
        remaining_days = max(total_days - days_elapsed, 0)
        projected_total = delivered + (daily_rate * remaining_days)

        if pace_pct < expected_pct * 0.8:
            status = "underdelivering"
        elif pace_pct > expected_pct * 1.2:
            status = "overdelivering"
        elif abs(pace_pct - expected_pct) < expected_pct * 0.05:
            status = "on_track"
        else:
            status = "slightly_off"

        return {
            "pace_pct": round(pace_pct, 4),
            "expected_pct": round(expected_pct, 4),
            "daily_rate": round(daily_rate, 4),
            "projected_total": round(projected_total, 4),
            "remaining_days": remaining_days,
            "status": status,
        }

    def analyze_campaign_pacing(
        self,
        campaign_df: pd.DataFrame,
        delivery_df: pd.DataFrame,
    ) -> Dict[str, Dict[str, Any]]:
        """Analyze pacing for each campaign.

        campaign_df columns: campaign_id, budget, start_date, end_date, target_impressions
        delivery_df columns: campaign_id, timestamp, impressions, spend

        Args:
            campaign_df: Campaign metadata.
            delivery_df: Delivery data.

        Returns:
            Dict keyed by campaign_id with pacing analysis results.
        """
        if campaign_df.empty:
            return {}

        results: Dict[str, Dict[str, Any]] = {}

        for _, campaign in campaign_df.iterrows():
            camp_id = campaign["campaign_id"]
            start_date = pd.to_datetime(campaign["start_date"])
            end_date = pd.to_datetime(campaign["end_date"])
            target_impressions = float(campaign.get("target_impressions", 0))
            budget = float(campaign.get("budget", 0))

            today = pd.Timestamp.now()
            total_days = max((end_date - start_date).days, 1)
            days_elapsed = max((today - start_date).days, 0)

            camp_delivery = delivery_df[delivery_df["campaign_id"] == camp_id].copy()

            if camp_delivery.empty:
                results[camp_id] = {
                    "impressions_pacing": self.calculate_pacing(
                        0, target_impressions, days_elapsed, total_days
                    ),
                    "spend_pacing": self.calculate_pacing(0, budget, days_elapsed, total_days),
                    "delivered_impressions": 0,
                    "total_spend": 0.0,
                    "days_elapsed": days_elapsed,
                    "total_days": total_days,
                }
                continue

            total_impressions = float(camp_delivery["impressions"].sum())
            total_spend = float(camp_delivery["spend"].sum()) if "spend" in camp_delivery.columns else 0.0

            imp_pacing = self.calculate_pacing(
                total_impressions, target_impressions, days_elapsed, total_days
            )
            spend_pacing = self.calculate_pacing(total_spend, budget, days_elapsed, total_days)

            projected_end = self._project_completion_date(
                delivered=total_impressions,
                target=target_impressions,
                start_date=start_date,
                daily_rate=imp_pacing["daily_rate"],
            )

            results[camp_id] = {
                "impressions_pacing": imp_pacing,
                "spend_pacing": spend_pacing,
                "delivered_impressions": total_impressions,
                "total_spend": total_spend,
                "days_elapsed": days_elapsed,
                "total_days": total_days,
                "projected_end_date": projected_end,
            }

        return results

    def detect_underdelivery(
        self,
        pacing_data: Dict[str, Dict[str, Any]],
        threshold: float = 0.8,
    ) -> List[Dict[str, Any]]:
        """Identify campaigns delivering below expected pace.

        Args:
            pacing_data: Output from analyze_campaign_pacing.
            threshold: Pace ratio below which campaigns are flagged (0.8 = 80%).

        Returns:
            List of dicts with campaign_id and delivery deficit info.
        """
        under: List[Dict[str, Any]] = []

        for camp_id, data in pacing_data.items():
            imp_pacing = data.get("impressions_pacing", {})
            pace_pct = imp_pacing.get("pace_pct", 0)
            expected_pct = imp_pacing.get("expected_pct", 100)

            if expected_pct > 0:
                pace_ratio = pace_pct / expected_pct
            else:
                pace_ratio = 0.0

            if pace_ratio < threshold:
                deficit_pct = round((1 - pace_ratio) * 100, 2)
                projected_total = imp_pacing.get("projected_total", 0)
                target = projected_total / pace_ratio if pace_ratio > 0 else 0
                deficit_units = round(target - projected_total, 0) if target > 0 else 0

                under.append(
                    {
                        "campaign_id": camp_id,
                        "pace_ratio": round(pace_ratio, 4),
                        "deficit_pct": deficit_pct,
                        "projected_total": round(projected_total, 0),
                        "estimated_deficit": deficit_units,
                        "status": imp_pacing.get("status", "unknown"),
                    }
                )

        under.sort(key=lambda x: x["pace_ratio"])
        return under

    def detect_overdelivery(
        self,
        pacing_data: Dict[str, Dict[str, Any]],
        threshold: float = 1.2,
    ) -> List[Dict[str, Any]]:
        """Identify campaigns delivering above expected pace.

        Args:
            pacing_data: Output from analyze_campaign_pacing.
            threshold: Pace ratio above which campaigns are flagged (1.2 = 120%).

        Returns:
            List of dicts with campaign_id and overdelivery info.
        """
        over: List[Dict[str, Any]] = []

        for camp_id, data in pacing_data.items():
            imp_pacing = data.get("impressions_pacing", {})
            pace_pct = imp_pacing.get("pace_pct", 0)
            expected_pct = imp_pacing.get("expected_pct", 100)

            if expected_pct > 0:
                pace_ratio = pace_pct / expected_pct
            else:
                pace_ratio = 0.0

            if pace_ratio > threshold:
                excess_pct = round((pace_ratio - 1) * 100, 2)
                projected_total = imp_pacing.get("projected_total", 0)

                over.append(
                    {
                        "campaign_id": camp_id,
                        "pace_ratio": round(pace_ratio, 4),
                        "excess_pct": excess_pct,
                        "projected_total": round(projected_total, 0),
                        "status": imp_pacing.get("status", "unknown"),
                    }
                )

        over.sort(key=lambda x: x["pace_ratio"], reverse=True)
        return over

    @staticmethod
    def calculate_budget_consumption(
        budget: float,
        spent: float,
        days_elapsed: int,
        total_days: int,
    ) -> Dict[str, Any]:
        """Calculate budget burn rate and projections.

        Args:
            budget: Total campaign budget.
            spent: Amount spent so far.
            days_elapsed: Days since campaign start.
            total_days: Total planned campaign duration.

        Returns:
            Dict with consumption_pct, daily_burn, projected_total, days_remaining,
            projected_overrun.
        """
        if budget <= 0 or total_days <= 0:
            return {
                "consumption_pct": 0.0,
                "daily_burn": 0.0,
                "projected_total": 0.0,
                "days_remaining": 0,
                "projected_overrun": 0.0,
                "status": "unknown",
            }

        consumption_pct = (spent / budget) * 100
        expected_pct = (days_elapsed / total_days) * 100

        daily_burn = spent / days_elapsed if days_elapsed > 0 else 0.0
        remaining_days = max(total_days - days_elapsed, 0)
        projected_total = spent + (daily_burn * remaining_days)
        projected_overrun = projected_total - budget

        if consumption_pct > expected_pct * 1.2:
            status = "burning_fast"
        elif consumption_pct < expected_pct * 0.8:
            status = "underspending"
        else:
            status = "on_track"

        return {
            "consumption_pct": round(consumption_pct, 4),
            "expected_pct": round(expected_pct, 4),
            "daily_burn": round(daily_burn, 4),
            "projected_total": round(projected_total, 4),
            "days_remaining": remaining_days,
            "projected_overrun": round(projected_overrun, 4),
            "status": status,
        }

    @staticmethod
    def _project_completion_date(
        delivered: float,
        target: float,
        start_date: pd.Timestamp,
        daily_rate: float,
    ) -> Optional[str]:
        """Project when delivery will reach target based on current daily rate.

        Args:
            delivered: Units delivered so far.
            target: Target units.
            start_date: Campaign start date.
            daily_rate: Current daily delivery rate.

        Returns:
            ISO date string of projected completion, or None if rate is zero.
        """
        if daily_rate <= 0 or target <= delivered:
            return None

        remaining = target - delivered
        days_needed = remaining / daily_rate
        projected_date = start_date + timedelta(days=days_needed)

        return projected_date.strftime("%Y-%m-%d")
