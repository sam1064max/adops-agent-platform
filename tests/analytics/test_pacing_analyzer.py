"""Tests for the PacingAnalyzer — campaign pacing and delivery detection."""

import numpy as np
import pandas as pd
import pytest

from src.analytics.pacing_analyzer import PacingAnalyzer


@pytest.fixture
def analyzer():
    return PacingAnalyzer()


# ---------------------------------------------------------------------------
# calculate_pacing (static)
# ---------------------------------------------------------------------------

class TestPacingCalculation:
    """Tests for PacingAnalyzer.calculate_pacing()."""

    def test_pacing_calculation(self, analyzer):
        result = analyzer.calculate_pacing(
            delivered=500_000,
            target=1_000_000,
            days_elapsed=15,
            total_days=30,
        )
        assert result["pace_pct"] == 50.0
        assert result["expected_pct"] == 50.0
        assert result["status"] == "on_track"
        assert result["daily_rate"] > 0

    def test_pacing_zero_target(self, analyzer):
        result = analyzer.calculate_pacing(
            delivered=100, target=0, days_elapsed=5, total_days=30
        )
        assert result["status"] == "unknown"
        assert result["pace_pct"] == 0.0

    def test_pacing_zero_total_days(self, analyzer):
        result = analyzer.calculate_pacing(
            delivered=100, target=1000, days_elapsed=5, total_days=0
        )
        assert result["status"] == "unknown"

    def test_pacing_underdelivering(self, analyzer):
        result = analyzer.calculate_pacing(
            delivered=100_000,
            target=1_000_000,
            days_elapsed=20,
            total_days=30,
        )
        assert result["status"] == "underdelivering"
        assert result["pace_pct"] < result["expected_pct"] * 0.8

    def test_pacing_overdelivering(self, analyzer):
        result = analyzer.calculate_pacing(
            delivered=900_000,
            target=1_000_000,
            days_elapsed=10,
            total_days=30,
        )
        assert result["status"] == "overdelivering"
        assert result["pace_pct"] > result["expected_pct"] * 1.2

    def test_pacing_projected_total(self, analyzer):
        result = analyzer.calculate_pacing(
            delivered=300_000,
            target=1_000_000,
            days_elapsed=10,
            total_days=30,
        )
        assert result["projected_total"] == 900_000.0

    def test_pacing_zero_days_elapsed(self, analyzer):
        result = analyzer.calculate_pacing(
            delivered=0, target=1_000_000, days_elapsed=0, total_days=30
        )
        assert result["daily_rate"] == 0.0
        # pace_pct=0, expected_pct=0 → falls through to slightly_off
        assert result["status"] in ("on_track", "slightly_off")


# ---------------------------------------------------------------------------
# detect_underdelivery
# ---------------------------------------------------------------------------

class TestDetectUnderdelivery:
    """Tests for under-delivery detection from pacing data."""

    def test_detect_underdelivery(self, analyzer):
        pacing_data = {
            "C1001": {
                "impressions_pacing": {
                    "pace_pct": 40.0,
                    "expected_pct": 80.0,
                    "projected_total": 500_000,
                    "status": "underdelivering",
                },
            },
            "C1002": {
                "impressions_pacing": {
                    "pace_pct": 95.0,
                    "expected_pct": 100.0,
                    "projected_total": 950_000,
                    "status": "on_track",
                },
            },
        }
        under = analyzer.detect_underdelivery(pacing_data, threshold=0.8)
        campaign_ids = [u["campaign_id"] for u in under]
        assert "C1001" in campaign_ids
        assert "C1002" not in campaign_ids

    def test_no_underdelivery_when_all_on_track(self, analyzer):
        pacing_data = {
            "C1001": {
                "impressions_pacing": {
                    "pace_pct": 100.0,
                    "expected_pct": 100.0,
                    "projected_total": 1_000_000,
                    "status": "on_track",
                },
            },
        }
        under = analyzer.detect_underdelivery(pacing_data, threshold=0.8)
        assert under == []

    def test_underdelivery_sorted_by_pace_ratio(self, analyzer):
        pacing_data = {
            "C1001": {"impressions_pacing": {"pace_pct": 30, "expected_pct": 100,
                                               "projected_total": 300_000, "status": "underdelivering"}},
            "C1002": {"impressions_pacing": {"pace_pct": 60, "expected_pct": 100,
                                               "projected_total": 600_000, "status": "underdelivering"}},
        }
        under = analyzer.detect_underdelivery(pacing_data, threshold=0.8)
        ratios = [u["pace_ratio"] for u in under]
        assert ratios == sorted(ratios)


# ---------------------------------------------------------------------------
# detect_overdelivery
# ---------------------------------------------------------------------------

class TestDetectOverdelivery:
    """Tests for over-delivery detection from pacing data."""

    def test_detect_overdelivery(self, analyzer):
        pacing_data = {
            "C1001": {
                "impressions_pacing": {
                    "pace_pct": 150.0,
                    "expected_pct": 100.0,
                    "projected_total": 1_500_000,
                    "status": "overdelivering",
                },
            },
            "C1002": {
                "impressions_pacing": {
                    "pace_pct": 90.0,
                    "expected_pct": 100.0,
                    "projected_total": 900_000,
                    "status": "on_track",
                },
            },
        }
        over = analyzer.detect_overdelivery(pacing_data, threshold=1.2)
        campaign_ids = [o["campaign_id"] for o in over]
        assert "C1001" in campaign_ids
        assert "C1002" not in campaign_ids

    def test_no_overdelivery_when_on_track(self, analyzer):
        pacing_data = {
            "C1001": {
                "impressions_pacing": {
                    "pace_pct": 100.0,
                    "expected_pct": 100.0,
                    "projected_total": 1_000_000,
                    "status": "on_track",
                },
            },
        }
        over = analyzer.detect_overdelivery(pacing_data, threshold=1.2)
        assert over == []

    def test_overdelivery_sorted_descending(self, analyzer):
        pacing_data = {
            "C1001": {"impressions_pacing": {"pace_pct": 130, "expected_pct": 100,
                                               "projected_total": 1_300_000, "status": "overdelivering"}},
            "C1002": {"impressions_pacing": {"pace_pct": 200, "expected_pct": 100,
                                               "projected_total": 2_000_000, "status": "overdelivering"}},
        }
        over = analyzer.detect_overdelivery(pacing_data, threshold=1.2)
        ratios = [o["pace_ratio"] for o in over]
        assert ratios == sorted(ratios, reverse=True)


# ---------------------------------------------------------------------------
# calculate_budget_consumption (static)
# ---------------------------------------------------------------------------

class TestBudgetConsumption:
    """Tests for PacingAnalyzer.calculate_budget_consumption()."""

    def test_budget_on_track(self, analyzer):
        result = analyzer.calculate_budget_consumption(
            budget=100_000, spent=50_000, days_elapsed=15, total_days=30
        )
        assert result["consumption_pct"] == 50.0
        assert result["status"] == "on_track"

    def test_budget_burning_fast(self, analyzer):
        result = analyzer.calculate_budget_consumption(
            budget=100_000, spent=80_000, days_elapsed=10, total_days=30
        )
        assert result["status"] == "burning_fast"
        assert result["projected_overrun"] > 0

    def test_budget_underspending(self, analyzer):
        result = analyzer.calculate_budget_consumption(
            budget=100_000, spent=10_000, days_elapsed=20, total_days=30
        )
        assert result["status"] == "underspending"

    def test_budget_zero(self, analyzer):
        result = analyzer.calculate_budget_consumption(
            budget=0, spent=0, days_elapsed=5, total_days=30
        )
        assert result["status"] == "unknown"
