"""Tests for the QueryAgent — classification and entity extraction."""

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Helpers: provide the missing Entity / TimeRange stubs that query_agent.py
# imports from src.models.schemas.  The production schemas.py only defines a
# bare TimeRange(start, end) — query_agent.py expects an extended version
# with a `relative` field and an Entity model.  We patch them in.
# ---------------------------------------------------------------------------

class _StubEntity:
    """Minimal Entity stand-in matching query_agent expectations."""
    def __init__(self, type: str, value: str, raw_text: str):
        self.type = type
        self.value = value
        self.raw_text = raw_text

    def model_dump(self):
        return {"type": self.type, "value": self.value, "raw_text": self.raw_text}


class _StubTimeRange:
    """Minimal TimeRange stand-in with a `relative` field."""
    def __init__(self, start: str, end: str, relative: str = "unknown"):
        self.start = start
        self.end = end
        self.relative = relative

    def model_dump(self):
        return {"start": self.start, "end": self.end, "relative": self.relative}


@pytest.fixture(autouse=True)
def _patch_schemas():
    """Inject stub Entity / TimeRange into the schemas module before import."""
    import src.models.schemas as _schemas_mod

    orig_entity = getattr(_schemas_mod, "Entity", None)
    orig_tr = getattr(_schemas_mod, "TimeRange", None)

    _schemas_mod.Entity = _StubEntity  # type: ignore[attr-defined]
    # Keep existing TimeRange but extend it for QueryAgent usage
    _schemas_mod.TimeRange = _StubTimeRange  # type: ignore[attr-defined]

    yield

    # Restore originals
    if orig_entity is not None:
        _schemas_mod.Entity = orig_entity  # type: ignore[assignment]
    if orig_tr is not None:
        _schemas_mod.TimeRange = orig_tr  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Import the agent (after schemas are patched)
# ---------------------------------------------------------------------------

from src.agents.query_agent import QueryAgent


# ---------------------------------------------------------------------------
# Classification tests
# ---------------------------------------------------------------------------

class TestClassifyIssue:
    """Tests for QueryAgent.classify_issue()."""

    def test_classify_fill_rate_issue(self, test_settings):
        with patch("src.agents.query_agent.settings", test_settings):
            agent = QueryAgent()
            result = agent.classify_issue("Why is the fill rate so low on campaign C1001?")
        assert result["issue_type"] == "fill_rate"

    def test_classify_ctr_issue(self, test_settings):
        with patch("src.agents.query_agent.settings", test_settings):
            agent = QueryAgent()
            result = agent.classify_issue("CTR has dropped significantly this week")
        assert result["issue_type"] == "ctr"

    def test_classify_underdelivery_issue(self, test_settings):
        with patch("src.agents.query_agent.settings", test_settings):
            agent = QueryAgent()
            result = agent.classify_issue("Campaign C2002 has underdelivery, not delivering impressions")
        assert result["issue_type"] == "underdelivery"

    def test_classify_general_question(self, test_settings):
        with patch("src.agents.query_agent.settings", test_settings):
            agent = QueryAgent()
            result = agent.classify_issue("What is the weather today?")
        assert result["issue_type"] == "general"


# ---------------------------------------------------------------------------
# Entity extraction tests
# ---------------------------------------------------------------------------

class TestExtractEntities:
    """Tests for entity extraction from free-text queries."""

    def test_extract_campaign_entities(self, test_settings):
        with patch("src.agents.query_agent.settings", test_settings):
            agent = QueryAgent()
            result = agent.classify_issue("Look at campaign C1001 and C2002")
        entity_values = [e["value"] for e in result["entities"]]
        entity_types = [e["type"] for e in result["entities"]]
        assert "1001" in entity_values
        assert "2002" in entity_values
        assert all(t == "campaign_id" for t in entity_types)

    def test_extract_inventory_id(self, test_settings):
        with patch("src.agents.query_agent.settings", test_settings):
            agent = QueryAgent()
            result = agent.classify_issue("Check inv_5555 performance")
        inv_entities = [e for e in result["entities"] if e["type"] == "inventory_id"]
        assert len(inv_entities) >= 1
        assert inv_entities[0]["value"] == "5555"

    def test_extract_numeric_id_with_prefix(self, test_settings):
        with patch("src.agents.query_agent.settings", test_settings):
            agent = QueryAgent()
            result = agent.classify_issue("Order #9876 is delayed")
        order_entities = [e for e in result["entities"] if e["type"] == "order_id"]
        assert len(order_entities) == 1
        assert order_entities[0]["value"] == "9876"

    def test_extract_multiple_entity_types(self, test_settings):
        with patch("src.agents.query_agent.settings", test_settings):
            agent = QueryAgent()
            result = agent.classify_issue(
                "Campaign C1001 on inventory inv_3333 has delivery issues"
            )
        types = {e["type"] for e in result["entities"]}
        assert "campaign_id" in types
        assert "inventory_id" in types


# ---------------------------------------------------------------------------
# Time range extraction tests
# ---------------------------------------------------------------------------

class TestExtractTimeRange:
    """Tests for time range resolution from free-text queries."""

    def test_extract_time_range_yesterday(self, test_settings):
        with patch("src.agents.query_agent.settings", test_settings):
            agent = QueryAgent()
            result = agent.classify_issue("What happened yesterday?")
        tr = result["time_range"]
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        expected = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        assert tr["start"] == expected
        assert tr["end"] == expected
        assert tr["relative"] == "yesterday"

    def test_extract_time_range_this_week(self, test_settings):
        with patch("src.agents.query_agent.settings", test_settings):
            agent = QueryAgent()
            result = agent.classify_issue("Show me this week's data")
        tr = result["time_range"]
        assert tr["relative"] == "this_week"

    def test_extract_time_range_last_7_days(self, test_settings):
        with patch("src.agents.query_agent.settings", test_settings):
            agent = QueryAgent()
            result = agent.classify_issue("Summary for the last 7 days")
        tr = result["time_range"]
        assert tr["relative"] == "last_7_days"
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        expected_start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        assert tr["start"] == expected_start

    def test_extract_time_range_absolute_date(self, test_settings):
        with patch("src.agents.query_agent.settings", test_settings):
            agent = QueryAgent()
            result = agent.classify_issue("Report for 2024-06-15")
        tr = result["time_range"]
        assert tr["start"] == "2024-06-15"
        assert tr["relative"] == "specific_date"

    def test_extract_time_range_fallback_default(self, test_settings):
        with patch("src.agents.query_agent.settings", test_settings):
            agent = QueryAgent()
            result = agent.classify_issue("Tell me about ads")
        tr = result["time_range"]
        assert tr["relative"] == "default_7_days"
