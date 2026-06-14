"""Shared fixtures for the AdOps Agent Platform test suite."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# Campaign / delivery / inventory sample data
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_campaign_data():
    """Return a dict representing a single campaign's metadata."""
    return {
        "campaign_id": "C1001",
        "name": "Summer Sale 2024",
        "advertiser": "Acme Corp",
        "status": "active",
        "budget": 50000.0,
        "spend": 23000.0,
        "impressions": 2_300_000,
        "clicks": 46_000,
        "conversions": 920,
        "start_date": "2024-06-01",
        "end_date": "2024-06-30",
        "target_impressions": 5_000_000,
    }


@pytest.fixture
def sample_delivery_data():
    """Return a DataFrame with 14 days of delivery metrics."""
    dates = pd.date_range("2024-06-01", periods=14, freq="D")
    rows = []
    for i, dt in enumerate(dates):
        imp = 150_000 + (i * 5_000)
        req = int(imp / 0.75)
        rows.append(
            {
                "timestamp": dt,
                "campaign_id": "C1001",
                "inventory_id": f"INV{i % 3 + 1:03d}",
                "impressions": imp,
                "ad_requests": req,
                "clicks": int(imp * 0.02),
                "spend": round(imp * 0.012, 2),
                "region": "US" if i % 2 == 0 else "EU",
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture
def sample_inventory_data():
    """Return a DataFrame describing three inventory sources."""
    return pd.DataFrame(
        {
            "inventory_id": ["INV001", "INV002", "INV003"],
            "publisher": ["PublisherA", "PublisherB", "PublisherC"],
            "domain": ["site-a.com", "site-b.com", "site-c.com"],
            "channel": ["web", "mobile", "app"],
            "region": ["US", "EU", "APAC"],
            "device_type": ["desktop", "mobile", "tablet"],
            "floor_price": [1.20, 0.80, 0.50],
            "viewability_rate": [0.72, 0.65, 0.58],
            "brand_safety_score": [0.95, 0.90, 0.88],
            "available_impressions": [500_000, 300_000, 200_000],
        }
    )


# ---------------------------------------------------------------------------
# Mock infrastructure
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_qdrant_client():
    """Return a mocked QdrantClient with common methods stubbed."""
    client = MagicMock()
    client.search.return_value = []
    client.get_collections.return_value = MagicMock(collections=[])
    client.upsert.return_value = None
    return client


@pytest.fixture
def mock_embedding_model():
    """Return a mocked SentenceTransformer embedding model."""
    model = MagicMock()
    model.get_sentence_embedding_dimension.return_value = 384
    model.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)
    return model


@pytest.fixture
def test_settings():
    """Return a mock Settings object with keyword/category maps for QueryAgent."""
    settings = MagicMock()
    settings.KEYWORD_MAP = {
        "fill_rate": ["fill rate", "fill-rate", "unfilled", "no fill", "inventory gap"],
        "ctr": ["ctr", "click-through", "click through", "low clicks", "no clicks"],
        "underdelivery": [
            "underdelivery",
            "under delivery",
            "under-delivery",
            "not delivering",
            "low impressions",
        ],
        "delivery_underperformance": [
            "delivery",
            "performance",
            "underperform",
            "low ctr",
        ],
        "pacing_anomaly": ["pacing", "pace", "behind pace", "ahead of pace"],
        "fraud_signal": ["fraud", "bot", "invalid traffic", "ivt"],
        "inventory_shortage": [
            "inventory shortage",
            "low inventory",
            "supply shortage",
            "no inventory",
        ],
        "creative_fatigue": [
            "creative fatigue",
            "fatigue",
            "declining ctr",
            "stale creative",
        ],
        "budget_depletion": [
            "budget depletion",
            "out of budget",
            "budget exhausted",
            "spend cap",
        ],
        "geo_mismatch": ["geo mismatch", "geo targeting", "wrong region"],
        "viewability_drop": ["viewability", "viewable", "not viewable"],
        "brand_safety": ["brand safety", "brand safe", "unsafe content"],
    }
    settings.ISSUE_CATEGORIES = [
        "fill_rate",
        "ctr",
        "underdelivery",
        "delivery_underperformance",
        "pacing_anomaly",
        "fraud_signal",
        "inventory_shortage",
        "creative_fatigue",
        "budget_depletion",
        "geo_mismatch",
        "viewability_drop",
        "brand_safety",
    ]
    return settings
