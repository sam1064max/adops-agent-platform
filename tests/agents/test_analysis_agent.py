"""Tests for the AnalysisAgent — root cause and recommendation generation."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def analysis_agent():
    from src.agents.analysis_agent import AnalysisAgent

    return AnalysisAgent(db_session_factory=MagicMock())


# ---------------------------------------------------------------------------
# analyse() core behaviour
# ---------------------------------------------------------------------------

class TestAnalysisAgent:
    """Tests for AnalysisAgent.analyse()."""

    def test_returns_root_cause_and_confidence(self, analysis_agent):
        context = {
            "snippets": [{"content": "Fill rate dropped 30% overnight"}],
            "campaign_context": [
                {"campaign_id": "C1001", "name": "Test", "impressions": 100_000}
            ],
            "inventory_context": [],
        }
        result = analysis_agent.analyse(
            issue_type="fill_rate",
            entities=[{"type": "campaign_id", "value": "1001"}],
            retrieval_context=context,
        )
        assert "root_cause" in result
        assert isinstance(result["root_cause"], str)
        assert 0.0 <= result["confidence"] <= 1.0
        assert isinstance(result["recommended_actions"], list)
        assert len(result["recommended_actions"]) > 0

    def test_confidence_increases_with_more_evidence(self, analysis_agent):
        context_few = {
            "snippets": [{"content": "Low fill rate"}],
            "campaign_context": [],
            "inventory_context": [],
        }
        context_many = {
            "snippets": [
                {"content": "Low fill rate on INV001"},
                {"content": "PublisherA reporting issues"},
                {"content": "Floor price increased 20%"},
                {"content": "Competitor bidding aggressively"},
                {"content": "Seasonal dip expected"},
            ],
            "campaign_context": [
                {"campaign_id": "C1001", "name": "A", "impressions": 50_000},
                {"campaign_id": "C1002", "name": "B", "impressions": 30_000},
            ],
            "inventory_context": [],
        }
        few = analysis_agent.analyse("fill_rate", [], context_few)
        many = analysis_agent.analyse("fill_rate", [], context_many)
        assert many["confidence"] >= few["confidence"]

    def test_recommendations_for_known_issue_type(self, analysis_agent):
        context = {"snippets": [], "campaign_context": [], "inventory_context": []}
        result = analysis_agent.analyse("fraud_signal", [], context)
        assert len(result["recommended_actions"]) >= 2
        assert any("fraud" in a.lower() or "review" in a.lower() or "flag" in a.lower()
                    for a in result["recommended_actions"])

    def test_general_issue_type_returns_generic_action(self, analysis_agent):
        context = {"snippets": [], "campaign_context": [], "inventory_context": []}
        result = analysis_agent.analyse("general", [], context)
        assert any("manually" in a.lower() or "review" in a.lower()
                    for a in result["recommended_actions"])

    def test_evidence_from_campaign_context(self, analysis_agent):
        context = {
            "snippets": [],
            "campaign_context": [
                {"campaign_id": "C500", "name": "Big Push", "impressions": 1_000_000,
                 "clicks": 20_000, "spend": 12_000, "status": "active"},
            ],
            "inventory_context": [],
        }
        result = analysis_agent.analyse("delivery_underperformance", [], context)
        evidence_texts = " ".join(result["evidence"])
        assert "C500" in evidence_texts
        assert "Big Push" in evidence_texts

    def test_evidence_from_inventory_context(self, analysis_agent):
        context = {
            "snippets": [],
            "campaign_context": [],
            "inventory_context": [
                {"inventory_id": "INV100", "publisher": "PublisherX",
                 "viewability_rate": 0.45, "floor_price": 2.50},
            ],
        }
        result = analysis_agent.analyse("inventory_shortage", [], context)
        evidence_texts = " ".join(result["evidence"])
        assert "INV100" in evidence_texts
        assert "PublisherX" in evidence_texts

    def test_empty_context_still_returns_valid_result(self, analysis_agent):
        context = {"snippets": [], "campaign_context": [], "inventory_context": []}
        result = analysis_agent.analyse("pacing_anomaly", [], context)
        assert result["confidence"] >= 0.0
        assert isinstance(result["root_cause"], str)
