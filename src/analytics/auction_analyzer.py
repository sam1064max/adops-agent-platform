"""Auction-level analysis for ad delivery diagnostics and competitive landscape."""

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


class AuctionAnalyzer:
    """Analyzes auction dynamics, bid landscapes, and competitive pressure."""

    @staticmethod
    def calculate_bid_rate(bids: float, ad_requests: float) -> float:
        """Calculate bid rate as a percentage.

        Args:
            bids: Number of bids submitted.
            ad_requests: Number of ad requests received.

        Returns:
            Bid rate as a percentage (0-100). Returns 0.0 if ad_requests is zero.
        """
        if ad_requests <= 0:
            return 0.0
        return round((bids / ad_requests) * 100, 4)

    @staticmethod
    def calculate_win_rate(wins: float, bids: float) -> float:
        """Calculate win rate as a percentage.

        Args:
            wins: Number of won auctions.
            bids: Number of bids submitted.

        Returns:
            Win rate as a percentage (0-100). Returns 0.0 if bids is zero.
        """
        if bids <= 0:
            return 0.0
        return round((wins / bids) * 100, 4)

    @staticmethod
    def calculate_ecpm(revenue: float, impressions: float) -> float:
        """Calculate effective CPM (revenue per thousand impressions).

        Args:
            revenue: Total revenue.
            impressions: Number of impressions served.

        Returns:
            eCPM value. Returns 0.0 if impressions is zero.
        """
        if impressions <= 0:
            return 0.0
        return round((revenue / impressions) * 1000, 4)

    @staticmethod
    def calculate_auction_pressure(
        total_bidders: float,
        available_inventory: float,
    ) -> float:
        """Calculate auction pressure as bidder-to-inventory ratio.

        Values > 1.0 indicate more bidders than available slots (high pressure).

        Args:
            total_bidders: Number of bidders competing.
            available_inventory: Number of available impression slots.

        Returns:
            Auction pressure ratio. Returns 0.0 if inventory is zero.
        """
        if available_inventory <= 0:
            return 0.0
        return round(total_bidders / available_inventory, 4)

    def analyze_auction_competitiveness(
        self,
        delivery_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """Analyze auction competitiveness metrics and trends.

        Expects delivery_df with columns:
            timestamp (datetime), bids (int), wins (int), ad_requests (int),
            impressions (int), revenue (float), bidders (int), inventory (int)

        Args:
            delivery_df: DataFrame with auction delivery metrics.

        Returns:
            Dict with bid_rate, win_rate, ecpm, pressure, trends.
        """
        df = delivery_df.copy()
        if df.empty:
            return self._empty_competitiveness()

        df = df.sort_values("timestamp").copy()
        df["date"] = pd.to_datetime(df["timestamp"]).dt.date

        daily = df.groupby("date").agg(
            bids=("bids", "sum"),
            wins=("wins", "sum"),
            ad_requests=("ad_requests", "sum"),
            impressions=("impressions", "sum"),
            revenue=("revenue", "sum"),
            bidders=("bidders", "mean") if "bidders" in df.columns else ("bids", "mean"),
            inventory=("inventory", "mean") if "inventory" in df.columns else ("impressions", "mean"),
        ).reset_index().sort_values("date")

        daily["bid_rate"] = daily.apply(
            lambda row: self.calculate_bid_rate(row["bids"], row["ad_requests"]),
            axis=1,
        )
        daily["win_rate"] = daily.apply(
            lambda row: self.calculate_win_rate(row["wins"], row["bids"]),
            axis=1,
        )
        daily["ecpm"] = daily.apply(
            lambda row: self.calculate_ecpm(row["revenue"], row["impressions"]),
            axis=1,
        )
        daily["pressure"] = daily.apply(
            lambda row: self.calculate_auction_pressure(row["bidders"], row["inventory"]),
            axis=1,
        )

        latest = daily.iloc[-1]
        latest_vals = {
            "bid_rate": float(latest["bid_rate"]),
            "win_rate": float(latest["win_rate"]),
            "ecpm": float(latest["ecpm"]),
            "pressure": float(latest["pressure"]),
        }

        trends = self._compute_trends(daily)

        return {
            "bid_rate": latest_vals["bid_rate"],
            "win_rate": latest_vals["win_rate"],
            "ecpm": latest_vals["ecpm"],
            "pressure": latest_vals["pressure"],
            "trends": trends,
            "daily_series": {
                "dates": [str(d) for d in daily["date"].values],
                "bid_rate": daily["bid_rate"].tolist(),
                "win_rate": daily["win_rate"].tolist(),
                "ecpm": daily["ecpm"].tolist(),
                "pressure": daily["pressure"].tolist(),
            },
        }

    def _compute_trends(self, daily: pd.DataFrame) -> Dict[str, Any]:
        """Compute directional trends for each metric in daily."""
        trends: Dict[str, str] = {}
        for metric in ["bid_rate", "win_rate", "ecpm", "pressure"]:
            values = daily[metric].values.astype(float)
            if len(values) < 2:
                trends[metric] = "stable"
                continue
            first_half = values[: len(values) // 2]
            second_half = values[len(values) // 2 :]
            first_mean = float(np.mean(first_half))
            second_mean = float(np.mean(second_half))
            if first_mean == 0:
                change_pct = 0.0
            else:
                change_pct = ((second_mean - first_mean) / first_mean) * 100
            if change_pct > 5:
                trends[metric] = "up"
            elif change_pct < -5:
                trends[metric] = "down"
            else:
                trends[metric] = "stable"
        return trends

    def _empty_competitiveness(self) -> Dict[str, Any]:
        return {
            "bid_rate": 0.0,
            "win_rate": 0.0,
            "ecpm": 0.0,
            "pressure": 0.0,
            "trends": {},
            "daily_series": {},
        }

    def detect_competitive_loss(
        self,
        df: pd.DataFrame,
        threshold: float = 0.15,
    ) -> List[Dict[str, Any]]:
        """Detect events where win rate drops significantly below baseline.

        Expects df with columns: timestamp (datetime), wins (int), bids (int),
        optionally: campaign_id, inventory_id.

        Args:
            df: DataFrame with bid/win data.
            threshold: Minimum proportional drop in win rate to flag (0.15 = 15%).

        Returns:
            List of loss event dicts with date, win_rate, baseline, drop_pct, context.
        """
        if df.empty:
            return []

        working = df.copy()
        working["date"] = pd.to_datetime(working["timestamp"]).dt.date

        daily = working.groupby("date").agg(
            wins=("wins", "sum"),
            bids=("bids", "sum"),
        ).reset_index().sort_values("date")

        daily["win_rate"] = daily.apply(
            lambda row: self.calculate_win_rate(row["wins"], row["bids"]),
            axis=1,
        )

        if len(daily) < 7:
            return []

        values = daily["win_rate"].values.astype(float)
        baseline = float(np.median(values))

        loss_events: List[Dict[str, Any]] = []
        for i in range(len(values)):
            curr = float(values[i])
            if baseline > 0:
                drop_pct = (baseline - curr) / baseline
            else:
                drop_pct = 0.0
            if drop_pct >= threshold:
                loss_events.append({
                    "date": str(daily.iloc[i]["date"]),
                    "win_rate": round(curr, 4),
                    "baseline": round(baseline, 4),
                    "drop_pct": round(drop_pct * 100, 2),
                })

        loss_events.sort(key=lambda x: x["drop_pct"], reverse=True)
        return loss_events

    def analyze_bid_landscape(
        self,
        delivery_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """Analyze bid distribution and identify top bidders.

        Expects delivery_df with columns: timestamp (datetime), bidder_id (str),
        bid_price (float), wins (int), bids (int), inventory_id (str).

        Args:
            delivery_df: DataFrame with bidder-level auction data.

        Returns:
            Dict with bid_distribution, top_bidders, concentration.
        """
        if delivery_df.empty:
            return {"bid_distribution": {}, "top_bidders": [], "concentration": 0.0}

        df = delivery_df.copy()

        if "bidder_id" not in df.columns:
            return {"bid_distribution": {}, "top_bidders": [], "concentration": 0.0}

        agg = df.groupby("bidder_id").agg(
            total_bids=("bids", "sum") if "bids" in df.columns else ("bidder_id", "count"),
            total_wins=("wins", "sum") if "wins" in df.columns else ("bidder_id", "count"),
            avg_bid_price=("bid_price", "mean") if "bid_price" in df.columns else ("bidder_id", "count"),
            max_bid_price=("bid_price", "max") if "bid_price" in df.columns else ("bidder_id", "count"),
        ).reset_index()

        agg["win_rate"] = agg.apply(
            lambda row: self.calculate_win_rate(row["total_wins"], row["total_bids"]),
            axis=1,
        )

        agg = agg.sort_values("total_bids", ascending=False).reset_index(drop=True)

        total_bids_all = float(agg["total_bids"].sum())
        bid_distribution: Dict[str, Any] = {}
        for price_bucket in ["low", "medium", "high"]:
            bid_distribution[price_bucket] = 0.0

        if "bid_price" in df.columns and not df["bid_price"].isna().all():
            prices = df["bid_price"].dropna().values.astype(float)
            if len(prices) > 0:
                low_cutoff = np.percentile(prices, 33)
                high_cutoff = np.percentile(prices, 66)
                bid_distribution["low"] = round(float(np.sum(prices <= low_cutoff)) / len(prices) * 100, 2)
                bid_distribution["medium"] = round(
                    float(np.sum((prices > low_cutoff) & (prices <= high_cutoff))) / len(prices) * 100, 2
                )
                bid_distribution["high"] = round(float(np.sum(prices > high_cutoff)) / len(prices) * 100, 2)

        top_bidders: List[Dict[str, Any]] = []
        for _, row in agg.head(10).iterrows():
            bid_share = round(float(row["total_bids"]) / total_bids_all * 100, 2) if total_bids_all > 0 else 0.0
            top_bidders.append({
                "bidder_id": row["bidder_id"],
                "total_bids": int(row["total_bids"]),
                "total_wins": int(row["total_wins"]),
                "win_rate": round(float(row["win_rate"]), 2),
                "avg_bid_price": round(float(row["avg_bid_price"]), 4) if row["avg_bid_price"] != row["bidder_id"] else 0.0,
                "bid_share_pct": bid_share,
            })

        top3_share = sum(b["bid_share_pct"] for b in top_bidders[:3]) if top_bidders else 0.0
        concentration = round(top3_share, 2)

        return {
            "bid_distribution": bid_distribution,
            "top_bidders": top_bidders,
            "concentration": concentration,
        }

    def detect_floor_price_issues(
        self,
        delivery_df: pd.DataFrame,
        inventory_df: pd.DataFrame,
    ) -> List[Dict[str, Any]]:
        """Detect floor price issues where bid prices fall below floor.

        Expects delivery_df with columns: inventory_id, bid_price (float),
        timestamp (datetime), impressions (int).
        Expects inventory_df with columns: inventory_id, floor_price (float).

        Args:
            delivery_df: Auction delivery data.
            inventory_df: Inventory metadata with floor prices.

        Returns:
            List of issue dicts with inventory_id, floor_price, avg_bid,
            below_floor_pct, severity.
        """
        if delivery_df.empty or inventory_df.empty:
            return []

        if "inventory_id" not in delivery_df.columns or "inventory_id" not in inventory_df.columns:
            return []

        if "bid_price" not in delivery_df.columns:
            return []

        if "floor_price" not in inventory_df.columns:
            return []

        merged = delivery_df.merge(
            inventory_df[["inventory_id", "floor_price"]],
            on="inventory_id",
            how="inner",
        )

        merged = merged.dropna(subset=["bid_price", "floor_price"])

        if merged.empty:
            return []

        merged["below_floor"] = merged["bid_price"] < merged["floor_price"]

        agg = merged.groupby("inventory_id").agg(
            avg_bid=("bid_price", "mean"),
            total_impressions=("impressions", "sum") if "impressions" in merged.columns else ("bid_price", "count"),
            below_floor_count=("below_floor", "sum"),
            total_auctions=("bid_price", "count"),
            floor_price=("floor_price", "first"),
        ).reset_index()

        issues: List[Dict[str, Any]] = []
        for _, row in agg.iterrows():
            total = float(row["total_auctions"])
            below = float(row["below_floor_count"])
            below_pct = round((below / total) * 100, 2) if total > 0 else 0.0

            floor_val = float(row["floor_price"])
            avg_bid = float(row["avg_bid"])

            if below_pct > 50:
                severity = "critical"
            elif below_pct > 20:
                severity = "high"
            elif below_pct > 5:
                severity = "medium"
            elif below_pct > 0:
                severity = "low"
            else:
                continue

            gap_pct = round((floor_val - avg_bid) / floor_val * 100, 2) if floor_val > 0 else 0.0

            issues.append({
                "inventory_id": str(row["inventory_id"]),
                "floor_price": round(floor_val, 4),
                "avg_bid": round(avg_bid, 4),
                "below_floor_pct": below_pct,
                "gap_pct": gap_pct if avg_bid < floor_val else 0.0,
                "severity": severity,
            })

        issues.sort(key=lambda x: x["below_floor_pct"], reverse=True)
        return issues
