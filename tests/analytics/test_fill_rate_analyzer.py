"""Tests for the FillRateAnalyzer — fill rate calculations and anomaly detection."""

import numpy as np
import pandas as pd
import pytest

from src.analytics.fill_rate_analyzer import FillRateAnalyzer


@pytest.fixture
def analyzer():
    return FillRateAnalyzer()


# ---------------------------------------------------------------------------
# calculate_fill_rate (static)
# ---------------------------------------------------------------------------

class TestFillRateCalculation:
    """Tests for FillRateAnalyzer.calculate_fill_rate()."""

    def test_fill_rate_calculation(self, analyzer):
        rate = analyzer.calculate_fill_rate(impressions=750, ad_requests=1000)
        assert rate == 75.0

    def test_fill_rate_zero_requests(self, analyzer):
        assert analyzer.calculate_fill_rate(impressions=100, ad_requests=0) == 0.0

    def test_fill_rate_zero_impressions(self, analyzer):
        assert analyzer.calculate_fill_rate(impressions=0, ad_requests=500) == 0.0

    def test_fill_rate_perfect(self, analyzer):
        assert analyzer.calculate_fill_rate(impressions=1000, ad_requests=1000) == 100.0

    def test_fill_rate_partial(self, analyzer):
        rate = analyzer.calculate_fill_rate(impressions=333, ad_requests=999)
        assert round(rate, 2) == 33.33

    def test_fill_rate_negative_requests_returns_zero(self, analyzer):
        assert analyzer.calculate_fill_rate(impressions=100, ad_requests=-10) == 0.0


# ---------------------------------------------------------------------------
# detect_sudden_drops
# ---------------------------------------------------------------------------

class TestDetectSuddenDrops:
    """Tests for drop detection in daily fill rates."""

    def test_detect_sudden_drops(self, analyzer):
        """A sharp drop from 80% to 30% should be flagged."""
        df = pd.DataFrame({
            "date": pd.date_range("2024-06-01", periods=5, freq="D"),
            "impressions": [8000, 8000, 8000, 8000, 3000],
            "ad_requests": [10000, 10000, 10000, 10000, 10000],
        })
        drops = analyzer.detect_sudden_drops(df, threshold=0.15)
        assert len(drops) >= 1
        assert drops[0]["previous_rate"] > drops[0]["current_rate"]
        assert drops[0]["drop_pct"] > 0

    def test_no_drops_when_stable(self, analyzer):
        """Stable fill rates should produce no drops."""
        df = pd.DataFrame({
            "date": pd.date_range("2024-06-01", periods=5, freq="D"),
            "impressions": [7500] * 5,
            "ad_requests": [10000] * 5,
        })
        drops = analyzer.detect_sudden_drops(df, threshold=0.15)
        assert drops == []

    def test_detects_multiple_drops(self, analyzer):
        """Two separate drops in a series."""
        df = pd.DataFrame({
            "date": pd.date_range("2024-06-01", periods=6, freq="D"),
            "impressions": [8000, 8000, 4000, 4000, 2000, 2000],
            "ad_requests": [10000, 10000, 10000, 10000, 10000, 10000],
        })
        drops = analyzer.detect_sudden_drops(df, threshold=0.15)
        assert len(drops) == 2

    def test_single_row_returns_empty(self, analyzer):
        df = pd.DataFrame({
            "date": ["2024-06-01"],
            "impressions": [5000],
            "ad_requests": [10000],
        })
        drops = analyzer.detect_sudden_drops(df, threshold=0.15)
        assert drops == []


# ---------------------------------------------------------------------------
# detect_inventory_shortages
# ---------------------------------------------------------------------------

class TestDetectInventoryShortages:
    """Tests for low-fill-rate inventory detection."""

    def test_detect_inventory_shortages(self, analyzer):
        df = pd.DataFrame({
            "inventory_id": ["INV001", "INV002", "INV003"],
            "impressions": [1000, 4000, 9000],
            "ad_requests": [10000, 10000, 10000],
        })
        shortages = analyzer.detect_inventory_shortages(df, min_fill_rate=50.0)
        ids = [s["inventory_id"] for s in shortages]
        assert "INV001" in ids  # 10% fill rate
        assert "INV002" in ids  # 40% fill rate
        assert "INV003" not in ids  # 90% — healthy

    def test_all_healthy_returns_empty(self, analyzer):
        df = pd.DataFrame({
            "inventory_id": ["INV001", "INV002"],
            "impressions": [8000, 9000],
            "ad_requests": [10000, 10000],
        })
        shortages = analyzer.detect_inventory_shortages(df, min_fill_rate=50.0)
        assert shortages == []

    def test_shortages_sorted_by_fill_rate(self, analyzer):
        df = pd.DataFrame({
            "inventory_id": ["INV001", "INV002", "INV003"],
            "impressions": [500, 2000, 3000],
            "ad_requests": [10000, 10000, 10000],
        })
        shortages = analyzer.detect_inventory_shortages(df, min_fill_rate=50.0)
        rates = [s["avg_fill_rate"] for s in shortages]
        assert rates == sorted(rates)

    def test_critical_vs_warning_status(self, analyzer):
        df = pd.DataFrame({
            "inventory_id": ["INV001", "INV002"],
            "impressions": [1000, 4000],
            "ad_requests": [10000, 10000],
        })
        shortages = analyzer.detect_inventory_shortages(df, min_fill_rate=50.0)
        status_map = {s["inventory_id"]: s["status"] for s in shortages}
        assert status_map["INV001"] == "critical"  # 10% < 25% (50% * 0.5)
        assert status_map["INV002"] == "warning"   # 40% >= 25%


# ---------------------------------------------------------------------------
# detect_request_spikes
# ---------------------------------------------------------------------------

class TestDetectRequestSpikes:
    """Tests for ad request volume spike detection."""

    def test_detect_request_spikes(self, analyzer):
        """A spike of 50 000 requests among ~10 000 should be flagged."""
        values = [10000] * 9 + [50000]
        df = pd.DataFrame({
            "date": pd.date_range("2024-06-01", periods=10, freq="D"),
            "ad_requests": values,
            "inventory_id": ["INV001"] * 10,
        })
        spikes = analyzer.detect_request_spikes(df, z_threshold=2.0)
        assert len(spikes) >= 1
        assert any(s["requests"] == 50000 for s in spikes)

    def test_no_spikes_when_stable(self, analyzer):
        df = pd.DataFrame({
            "date": pd.date_range("2024-06-01", periods=10, freq="D"),
            "ad_requests": [10000] * 10,
            "inventory_id": ["INV001"] * 10,
        })
        spikes = analyzer.detect_request_spikes(df, z_threshold=2.0)
        assert spikes == []

    def test_spike_without_inventory_column(self, analyzer):
        """Should handle missing inventory_id gracefully."""
        values = [5000] * 9 + [30000]
        df = pd.DataFrame({
            "date": pd.date_range("2024-06-01", periods=10, freq="D"),
            "ad_requests": values,
        })
        spikes = analyzer.detect_request_spikes(df, z_threshold=2.0)
        assert len(spikes) >= 1
        assert spikes[0]["inventory_id"] == "unknown"

    def test_too_few_data_points_skipped(self, analyzer):
        """Z-score needs at least 3 data points per inventory."""
        df = pd.DataFrame({
            "date": pd.date_range("2024-06-01", periods=2, freq="D"),
            "ad_requests": [1000, 50000],
            "inventory_id": ["INV001"] * 2,
        })
        spikes = analyzer.detect_request_spikes(df, z_threshold=2.0)
        assert spikes == []


# ---------------------------------------------------------------------------
# analyze_fill_rate (integration)
# ---------------------------------------------------------------------------

class TestAnalyzeFillRate:
    """Integration tests for analyze_fill_rate()."""

    def test_returns_trend_and_anomalies(self, analyzer, sample_delivery_data):
        result = analyzer.analyze_fill_rate(sample_delivery_data, campaign_id="C1001")
        assert "current_rate" in result
        assert "trend" in result
        assert result["trend"] in ("stable", "improving", "declining")
        assert isinstance(result["anomalies"], list)

    def test_filters_by_campaign_id(self, analyzer, sample_delivery_data):
        result = analyzer.analyze_fill_rate(sample_delivery_data, campaign_id="C9999")
        assert result["current_rate"] == 0.0
        assert result["trend"] == "stable"
