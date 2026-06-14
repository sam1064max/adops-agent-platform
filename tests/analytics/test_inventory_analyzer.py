"""Tests for the InventoryAnalyzer — inventory health and inactive detection."""

import numpy as np
import pandas as pd
import pytest

from src.analytics.inventory_analyzer import InventoryAnalyzer


@pytest.fixture
def analyzer():
    return InventoryAnalyzer()


@pytest.fixture
def delivery_df():
    """DataFrame with 14 days of delivery data for 3 inventory sources."""
    dates = pd.date_range("2024-06-01", periods=14, freq="D")
    rows = []
    for dt in dates:
        for inv_id in ["INV001", "INV002", "INV003"]:
            base_imp = {"INV001": 50_000, "INV002": 30_000, "INV003": 10_000}[inv_id]
            rows.append({
                "timestamp": dt,
                "inventory_id": inv_id,
                "impressions": base_imp,
                "ad_requests": int(base_imp / 0.7),
                "clicks": int(base_imp * 0.02),
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# get_inventory_health_score
# ---------------------------------------------------------------------------

class TestInventoryHealthScore:
    """Tests for single-inventory health scoring."""

    def test_inventory_health_score(self, analyzer):
        score = analyzer.get_inventory_health_score("INV001", {
            "fill_rate": 80.0,
            "ctr": 2.0,
            "impressions": 100_000,
            "ad_requests": 125_000,
        })
        assert 0 <= score <= 100
        assert score > 50  # healthy inventory should score well

    def test_health_score_low_fill_rate(self, analyzer):
        score = analyzer.get_inventory_health_score("INV001", {
            "fill_rate": 10.0,
            "ctr": 0.5,
            "impressions": 5_000,
            "ad_requests": 50_000,
        })
        assert score < 50

    def test_health_score_perfect(self, analyzer):
        score = analyzer.get_inventory_health_score("INV001", {
            "fill_rate": 100.0,
            "ctr": 5.0,
            "impressions": 100_000,
            "ad_requests": 100_000,
        })
        assert score >= 90

    def test_health_score_zero_requests(self, analyzer):
        score = analyzer.get_inventory_health_score("INV001", {
            "fill_rate": 0.0,
            "ctr": 0.0,
            "impressions": 0,
            "ad_requests": 0,
        })
        assert score == 0.0


# ---------------------------------------------------------------------------
# detect_inactive_inventory
# ---------------------------------------------------------------------------

class TestDetectInactiveInventory:
    """Tests for inactive inventory source detection."""

    def test_detect_inactive_inventory(self, analyzer, delivery_df):
        inventory_df = pd.DataFrame({
            "inventory_id": ["INV001", "INV002", "INV003", "INV004"],
            "publisher": ["A", "B", "C", "D"],
            "channel": ["web", "mobile", "app", "web"],
            "region": ["US", "EU", "APAC", "US"],
            "device_type": ["desktop", "mobile", "tablet", "desktop"],
        })
        inactive = analyzer.detect_inactive_inventory(inventory_df, delivery_df, lookback_days=7)
        inactive_ids = [i["inventory_id"] for i in inactive]
        # INV004 has no delivery data at all
        assert "INV004" in inactive_ids
        # INV001-003 are active in the delivery data
        assert "INV001" not in inactive_ids

    def test_all_active_returns_empty(self, analyzer, delivery_df):
        inventory_df = pd.DataFrame({
            "inventory_id": ["INV001", "INV002", "INV003"],
            "publisher": ["A", "B", "C"],
            "channel": ["web", "mobile", "app"],
            "region": ["US", "EU", "APAC"],
            "device_type": ["desktop", "mobile", "tablet"],
        })
        inactive = analyzer.detect_inactive_inventory(inventory_df, delivery_df, lookback_days=14)
        assert inactive == []

    def test_inactive_sorted_by_days(self, analyzer):
        """Inventory with no data at all should have the most days inactive."""
        base_date = pd.Timestamp("2024-06-14")
        inventory_df = pd.DataFrame({
            "inventory_id": ["INV001", "INV002"],
            "publisher": ["A", "B"],
            "channel": ["web", "mobile"],
            "region": ["US", "EU"],
            "device_type": ["desktop", "mobile"],
        })
        delivery_df = pd.DataFrame({
            "timestamp": [base_date - pd.Timedelta(days=20)],
            "inventory_id": ["INV001"],
            "impressions": [5000],
            "ad_requests": [10000],
            "clicks": [100],
        })
        inactive = analyzer.detect_inactive_inventory(inventory_df, delivery_df, lookback_days=7)
        days = [i["days_inactive"] for i in inactive]
        assert days == sorted(days, reverse=True)


# ---------------------------------------------------------------------------
# analyze_inventory (integration)
# ---------------------------------------------------------------------------

class TestAnalyzeInventory:
    """Integration tests for analyze_inventory()."""

    def test_returns_overall_health(self, analyzer, delivery_df, sample_inventory_data):
        result = analyzer.analyze_inventory(sample_inventory_data, delivery_df)
        assert "overall_health" in result
        assert "inventory_scores" in result
        assert "aggregates" in result
        assert 0 <= result["overall_health"] <= 100

    def test_empty_inputs(self, analyzer):
        empty_inv = pd.DataFrame(columns=["inventory_id", "publisher", "channel",
                                           "region", "device_type"])
        empty_del = pd.DataFrame(columns=["inventory_id", "timestamp", "impressions",
                                           "ad_requests", "clicks"])
        result = analyzer.analyze_inventory(empty_inv, empty_del)
        assert result["overall_health"] == 0.0
        assert result["inventory_scores"] == {}

    def test_per_inventory_scores_present(self, analyzer, delivery_df, sample_inventory_data):
        result = analyzer.analyze_inventory(sample_inventory_data, delivery_df)
        for inv_id in ["INV001", "INV002", "INV003"]:
            assert inv_id in result["inventory_scores"]
            score_entry = result["inventory_scores"][inv_id]
            assert "health_score" in score_entry
            assert "fill_rate" in score_entry
            assert "ctr" in score_entry


# ---------------------------------------------------------------------------
# analyze_regional_issues
# ---------------------------------------------------------------------------

class TestAnalyzeRegionalIssues:
    """Tests for region-level delivery analysis."""

    def test_returns_region_breakdown(self, analyzer, delivery_df, sample_inventory_data):
        result = analyzer.analyze_regional_issues(delivery_df, sample_inventory_data)
        assert len(result) > 0
        for region, data in result.items():
            assert "impressions" in data
            assert "fill_rate" in data
            assert "health" in data
            assert data["health"] in ("poor", "below_average", "normal", "excellent")

    def test_empty_inventory_returns_empty(self, analyzer, delivery_df):
        empty_inv = pd.DataFrame(columns=["inventory_id", "region"])
        result = analyzer.analyze_regional_issues(delivery_df, empty_inv)
        assert result == {}
