"""Fill rate analysis for ad operations monitoring and alerting."""

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


class FillRateAnalyzer:
    """Analyzes ad fill rates, detects anomalies, and identifies inventory issues."""

    @staticmethod
    def calculate_fill_rate(impressions: float, ad_requests: float) -> float:
        """Calculate fill rate as a percentage.

        Args:
            impressions: Number of served impressions.
            ad_requests: Number of ad requests received.

        Returns:
            Fill rate as a percentage (0-100). Returns 0.0 if ad_requests is zero.
        """
        if ad_requests <= 0:
            return 0.0
        return round((impressions / ad_requests) * 100, 4)

    def analyze_fill_rate(
        self,
        delivery_df: pd.DataFrame,
        campaign_id: Optional[str] = None,
        time_range: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Analyze fill rate trends, changes, and anomalies.

        Expects delivery_df with columns:
            timestamp (datetime), impressions (int), ad_requests (int),
            campaign_id (str), inventory_id (str), region (str)

        Args:
            delivery_df: DataFrame with delivery metrics.
            campaign_id: Optional campaign filter.
            time_range: Optional dict with 'start' and 'end' date strings.

        Returns:
            Dict with current_rate, previous_rate, change_pct, trend, anomalies.
        """
        df = delivery_df.copy()

        if campaign_id is not None:
            df = df[df["campaign_id"] == campaign_id]

        if time_range is not None:
            if "start" in time_range:
                df = df[df["timestamp"] >= pd.to_datetime(time_range["start"])]
            if "end" in time_range:
                df = df[df["timestamp"] <= pd.to_datetime(time_range["end"])]

        if df.empty:
            return {
                "current_rate": 0.0,
                "previous_rate": 0.0,
                "change_pct": 0.0,
                "trend": "stable",
                "anomalies": [],
            }

        df = df.sort_values("timestamp").copy()
        df["date"] = pd.to_datetime(df["timestamp"]).dt.date

        daily = df.groupby("date").agg(
            impressions=("impressions", "sum"),
            ad_requests=("ad_requests", "sum"),
        ).reset_index()

        daily["fill_rate"] = daily.apply(
            lambda row: self.calculate_fill_rate(
                row["impressions"], row["ad_requests"]
            ),
            axis=1,
        )

        if len(daily) < 2:
            return {
                "current_rate": float(daily["fill_rate"].iloc[-1]),
                "previous_rate": float(daily["fill_rate"].iloc[-1]),
                "change_pct": 0.0,
                "trend": "stable",
                "anomalies": [],
            }

        current_rate = float(daily["fill_rate"].iloc[-1])
        previous_rate = float(daily["fill_rate"].iloc[-2])
        change_pct = round(
            ((current_rate - previous_rate) / previous_rate * 100)
            if previous_rate != 0
            else 0.0,
            4,
        )

        rates = daily["fill_rate"].values
        mean_rate = np.mean(rates)
        std_rate = np.std(rates) if len(rates) > 1 else 0.0

        if std_rate > 0:
            z_current = (current_rate - mean_rate) / std_rate
        else:
            z_current = 0.0

        if z_current > 1.5:
            trend = "improving"
        elif z_current < -1.5:
            trend = "declining"
        else:
            trend = "stable"

        anomalies = self.detect_sudden_drops(daily, threshold=0.15)

        return {
            "current_rate": round(current_rate, 4),
            "previous_rate": round(previous_rate, 4),
            "change_pct": round(change_pct, 4),
            "trend": trend,
            "anomalies": anomalies,
        }

    def detect_sudden_drops(
        self, df: pd.DataFrame, threshold: float = 0.15
    ) -> List[Dict[str, Any]]:
        """Detect sudden drops in fill rate exceeding a percentage threshold.

        Expects df with columns: date (or timestamp), impressions, ad_requests.

        Args:
            df: DataFrame with delivery data.
            threshold: Minimum percentage drop to flag (0.15 = 15%).

        Returns:
            List of dicts with date, previous_rate, current_rate, drop_pct.
        """
        working = df.copy()

        if "fill_rate" not in working.columns:
            if "date" in working.columns:
                working = working.sort_values("date")
            elif "timestamp" in working.columns:
                working["date"] = pd.to_datetime(working["timestamp"]).dt.date
                working = working.sort_values("date")

            daily = (
                working.groupby("date")
                .agg(impressions=("impressions", "sum"), ad_requests=("ad_requests", "sum"))
                .reset_index()
            )
            daily["fill_rate"] = daily.apply(
                lambda row: self.calculate_fill_rate(row["impressions"], row["ad_requests"]),
                axis=1,
            )
        else:
            daily = working.copy()
            daily = daily.sort_values(daily.columns[0])

        if len(daily) < 2:
            return []

        rates = daily["fill_rate"].values
        dates = daily.iloc[:, 0].values

        drops: List[Dict[str, Any]] = []
        for i in range(1, len(rates)):
            prev_rate = float(rates[i - 1])
            curr_rate = float(rates[i])
            if prev_rate > 0:
                drop_pct = (prev_rate - curr_rate) / prev_rate
            else:
                drop_pct = 0.0

            if drop_pct >= threshold:
                drops.append(
                    {
                        "date": str(dates[i]),
                        "previous_rate": round(prev_rate, 4),
                        "current_rate": round(curr_rate, 4),
                        "drop_pct": round(drop_pct * 100, 2),
                    }
                )

        return drops

    def detect_inventory_shortages(
        self, df: pd.DataFrame, min_fill_rate: float = 50.0
    ) -> List[Dict[str, Any]]:
        """Identify inventory sources with persistently low fill rates.

        Expects df with columns: inventory_id, impressions, ad_requests.

        Args:
            df: DataFrame with delivery data.
            min_fill_rate: Minimum fill rate threshold (percentage) to consider healthy.

        Returns:
            List of dicts with inventory_id, avg_fill_rate, total_requests, status.
        """
        if df.empty or "inventory_id" not in df.columns:
            return []

        agg = df.groupby("inventory_id").agg(
            impressions=("impressions", "sum"),
            ad_requests=("ad_requests", "sum"),
        ).reset_index()

        agg["fill_rate"] = agg.apply(
            lambda row: self.calculate_fill_rate(row["impressions"], row["ad_requests"]),
            axis=1,
        )

        low_fill = agg[agg["fill_rate"] < min_fill_rate]

        shortages: List[Dict[str, Any]] = []
        for _, row in low_fill.iterrows():
            status = "critical" if row["fill_rate"] < min_fill_rate * 0.5 else "warning"
            shortages.append(
                {
                    "inventory_id": row["inventory_id"],
                    "avg_fill_rate": round(float(row["fill_rate"]), 4),
                    "total_requests": int(row["ad_requests"]),
                    "status": status,
                }
            )

        shortages.sort(key=lambda x: x["avg_fill_rate"])
        return shortages

    def detect_request_spikes(
        self, df: pd.DataFrame, z_threshold: float = 2.0
    ) -> List[Dict[str, Any]]:
        """Detect unusual spikes in ad request volume using z-scores.

        Expects df with columns: timestamp (or date), ad_requests, inventory_id.

        Args:
            df: DataFrame with request data.
            z_threshold: Z-score threshold to flag as spike.

        Returns:
            List of dicts with date, inventory_id, requests, z_score.
        """
        working = df.copy()

        if "date" not in working.columns:
            if "timestamp" in working.columns:
                working["date"] = pd.to_datetime(working["timestamp"]).dt.date

        if "inventory_id" not in working.columns:
            working["inventory_id"] = "unknown"

        agg = (
            working.groupby(["date", "inventory_id"])
            .agg(ad_requests=("ad_requests", "sum"))
            .reset_index()
        )

        spikes: List[Dict[str, Any]] = []
        for inv_id, group in agg.groupby("inventory_id"):
            if len(group) < 3:
                continue

            values = group["ad_requests"].values.astype(float)
            mean = np.mean(values)
            std = np.std(values)

            if std == 0:
                continue

            z_scores = (values - mean) / std
            spike_mask = np.abs(z_scores) >= z_threshold

            for idx in np.where(spike_mask)[0]:
                row = group.iloc[idx]
                spikes.append(
                    {
                        "date": str(row["date"]),
                        "inventory_id": inv_id,
                        "requests": int(row["ad_requests"]),
                        "z_score": round(float(z_scores[idx]), 4),
                    }
                )

        spikes.sort(key=lambda x: abs(x["z_score"]), reverse=True)
        return spikes
