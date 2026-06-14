"""Tests for the CTRAnalyzer — CTR calculations and creative fatigue detection."""

import numpy as np
import pandas as pd
import pytest

from src.analytics.ctr_analyzer import CTRAnalyzer


@pytest.fixture
def analyzer():
    return CTRAnalyzer()


# ---------------------------------------------------------------------------
# calculate_ctr (static)
# ---------------------------------------------------------------------------

class TestCTRCalculation:
    """Tests for CTRAnalyzer.calculate_ctr()."""

    def test_ctr_calculation(self, analyzer):
        assert analyzer.calculate_ctr(clicks=200, impressions=10000) == 2.0

    def test_ctr_zero_impressions(self, analyzer):
        assert analyzer.calculate_ctr(clicks=50, impressions=0) == 0.0

    def test_ctr_zero_clicks(self, analyzer):
        assert analyzer.calculate_ctr(clicks=0, impressions=10000) == 0.0

    def test_ctr_perfect(self, analyzer):
        assert analyzer.calculate_ctr(clicks=100, impressions=100) == 100.0

    def test_ctr_small_values(self, analyzer):
        rate = analyzer.calculate_ctr(clicks=1, impressions=3)
        assert round(rate, 2) == 33.33

    def test_ctr_negative_impressions_returns_zero(self, analyzer):
        assert analyzer.calculate_ctr(clicks=10, impressions=-5) == 0.0


# ---------------------------------------------------------------------------
# detect_creative_fatigue
# ---------------------------------------------------------------------------

class TestDetectCreativeFatigue:
    """Tests for rolling-window creative fatigue detection."""

    def test_detect_creative_fatigue(self, analyzer):
        """Declining CTR over two 7-day windows should flag fatigue."""
        np.random.seed(42)
        n = 20
        dates = pd.date_range("2024-06-01", periods=n, freq="D")
        # First 10 days: high CTR (~3%), last 10: low CTR (~1%)
        ctrs = [3.0] * 10 + [1.0] * 10
        impressions = [10000] * n
        clicks = [int(c / 100 * imp) for c, imp in zip(ctrs, impressions)]

        df = pd.DataFrame({
            "timestamp": dates,
            "clicks": clicks,
            "impressions": impressions,
            "creative_id": ["CR001"] * n,
        })
        result = analyzer.detect_creative_fatigue(df, window=7)
        assert result["fatigued"] is True
        assert result["fatigue_score"] > 0.15
        assert result["details"]["recent_window_avg"] < result["details"]["earlier_window_avg"]

    def test_no_fatigue_when_stable(self, analyzer):
        """Stable CTR should not flag fatigue."""
        n = 20
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-06-01", periods=n, freq="D"),
            "clicks": [200] * n,
            "impressions": [10000] * n,
            "creative_id": ["CR001"] * n,
        })
        result = analyzer.detect_creative_fatigue(df, window=7)
        assert result["fatigued"] is False
        assert result["fatigue_score"] == 0.0

    def test_insufficient_data(self, analyzer):
        """Fewer than window*2 days should return insufficient_data."""
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-06-01", periods=5, freq="D"),
            "clicks": [100] * 5,
            "impressions": [10000] * 5,
            "creative_id": ["CR001"] * 5,
        })
        result = analyzer.detect_creative_fatigue(df, window=7)
        assert result["fatigued"] is False
        assert result["details"]["reason"] == "insufficient_data"

    def test_empty_dataframe(self, analyzer):
        df = pd.DataFrame(columns=["timestamp", "clicks", "impressions", "creative_id"])
        result = analyzer.detect_creative_fatigue(df, window=7)
        assert result["fatigued"] is False

    def test_fatigue_score_bounded(self, analyzer):
        """Fatigue score should always be between 0 and 1."""
        n = 20
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-06-01", periods=n, freq="D"),
            "clicks": list(range(500, 500 + n)),
            "impressions": [10000] * n,
            "creative_id": ["CR001"] * n,
        })
        result = analyzer.detect_creative_fatigue(df, window=7)
        assert 0.0 <= result["fatigue_score"] <= 1.0


# ---------------------------------------------------------------------------
# analyze_ctr
# ---------------------------------------------------------------------------

class TestAnalyzeCTR:
    """Integration tests for CTRAnalyzer.analyze_ctr()."""

    def test_returns_current_and_previous_ctr(self, analyzer):
        n = 10
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-06-01", periods=n, freq="D"),
            "clicks": [200] * n,
            "impressions": [10000] * n,
            "campaign_id": ["C1001"] * n,
            "creative_id": ["CR001"] * n,
            "segment": ["default"] * n,
            "inventory_id": ["INV001"] * n,
        })
        result = analyzer.analyze_ctr(df, campaign_id="C1001")
        assert result["current_ctr"] == 2.0
        assert result["previous_ctr"] == 2.0
        assert result["trend"] in ("stable", "improving", "declining", "volatile")

    def test_empty_df_returns_zeros(self, analyzer):
        df = pd.DataFrame(columns=["timestamp", "clicks", "impressions",
                                    "campaign_id", "creative_id", "segment",
                                    "inventory_id"])
        result = analyzer.analyze_ctr(df)
        assert result["current_ctr"] == 0.0
        assert result["trend"] == "stable"

    def test_diagnostics_include_creative_breakdown(self, analyzer):
        n = 5
        df = pd.DataFrame({
            "timestamp": pd.date_range("2024-06-01", periods=n, freq="D"),
            "clicks": [100, 150, 200, 250, 300],
            "impressions": [10000] * n,
            "campaign_id": ["C1001"] * n,
            "creative_id": ["CR001", "CR001", "CR002", "CR002", "CR002"],
            "segment": ["seg_a", "seg_a", "seg_b", "seg_b", "seg_b"],
            "inventory_id": ["INV001"] * n,
        })
        result = analyzer.analyze_ctr(df, campaign_id="C1001")
        diag = result["diagnostics"]
        assert "best_creative" in diag
        assert "worst_creative" in diag
        assert "segment_breakdown" in diag
