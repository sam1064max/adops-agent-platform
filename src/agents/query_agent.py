"""Query classification agent for AdOps issues.

Classifies incoming natural language queries into issue categories,
extracts entities (campaign IDs, inventory IDs, dates), and resolves
time references into concrete date ranges.
"""

import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from src.config.settings import settings
from src.models.schemas import Entity, QueryClassification, TimeRange


class QueryAgent:
    """Classifies ad operations queries and extracts structured entities.

    Uses keyword matching and regex to categorize issues into predefined
    buckets (fill_rate, ctr, underdelivery, etc.) and extracts campaign IDs,
    inventory IDs, and time references from free-text queries.
    """

    CAMPAIGN_ID_PATTERN = re.compile(
        r"\bC(\d{3,10})\b", re.IGNORECASE
    )
    INVENTORY_ID_PATTERN = re.compile(
        r"\b(?:inv|inventory|adunit|ad[_\s]?unit)[_\-\s]?(\d{3,10})\b",
        re.IGNORECASE,
    )
    NUMERIC_ID_PATTERN = re.compile(
        r"\b(?:campaign|advertiser|order|line\s?item)\s*[#:\s]*(\d{4,10})\b",
        re.IGNORECASE,
    )
    DATE_PATTERN = re.compile(
        r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b"
    )
    DATE_RANGE_PATTERN = re.compile(
        r"\b(\d{1,2}[-/]\d{1,2})\s*(?:to|-)\s*(\d{1,2}[-/]\d{1,2})\b"
    )

    def __init__(self) -> None:
        self.keyword_map = settings.KEYWORD_MAP
        self.categories = settings.ISSUE_CATEGORIES

    def classify_issue(self, text: str) -> Dict:
        """Classify an ad ops query and extract entities.

        Args:
            text: Free-text user query about an ad operations issue.

        Returns:
            Dict with keys: issue_type, entities, time_range.
        """
        lowered = text.lower()
        issue_type = self._detect_issue_type(lowered)
        entities = self._extract_entities(text)
        time_range = self._extract_time_range(text, lowered)

        return {
            "issue_type": issue_type,
            "entities": [e.model_dump() for e in entities],
            "time_range": time_range.model_dump(),
        }

    def _detect_issue_type(self, text: str) -> str:
        """Score each category by keyword hits, return best match."""
        scores: Dict[str, int] = {cat: 0 for cat in self.categories}
        for category, keywords in self.keyword_map.items():
            for kw in keywords:
                if kw.lower() in text:
                    scores[category] += 1

        best = max(scores, key=scores.get)  # type: ignore[arg-type]
        if scores[best] == 0:
            return "general"
        return best

    def _extract_entities(self, text: str) -> List[Entity]:
        """Pull campaign IDs, inventory IDs, and other numeric identifiers."""
        entities: List[Entity] = []

        for match in self.CAMPAIGN_ID_PATTERN.finditer(text):
            entities.append(Entity(
                type="campaign_id",
                value=match.group(1),
                raw_text=match.group(0),
            ))

        for match in self.INVENTORY_ID_PATTERN.finditer(text):
            entities.append(Entity(
                type="inventory_id",
                value=match.group(1),
                raw_text=match.group(0),
            ))

        for match in self.NUMERIC_ID_PATTERN.finditer(text):
            raw = match.group(0).lower()
            if "campaign" in raw:
                etype = "campaign_id"
            elif "advertiser" in raw:
                etype = "advertiser_id"
            elif "order" in raw:
                etype = "order_id"
            else:
                etype = "line_item_id"
            entities.append(Entity(
                type=etype,
                value=match.group(1),
                raw_text=match.group(0),
            ))

        return entities

    def _extract_time_range(self, raw_text: str, lowered: str) -> TimeRange:
        """Resolve relative and absolute time references to a date range."""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # explicit date range like "06/01 to 06/14"
        dr_match = self.DATE_RANGE_PATTERN.search(raw_text)
        if dr_match:
            year = today.year
            start_str = f"{year}-{dr_match.group(1).replace('/', '-')}"
            end_str = f"{year}-{dr_match.group(2).replace('/', '-')}"
            return TimeRange(start=start_str, end=end_str, relative="custom_range")

        # absolute date
        date_match = self.DATE_PATTERN.search(raw_text)
        if date_match:
            d = date_match.group(1).replace("/", "-")
            return TimeRange(start=d, end=d, relative="specific_date")

        # relative keywords
        if "yesterday" in lowered:
            d = (today - timedelta(days=1)).strftime("%Y-%m-%d")
            return TimeRange(start=d, end=d, relative="yesterday")

        if "today" in lowered:
            d = today.strftime("%Y-%m-%d")
            return TimeRange(start=d, end=d, relative="today")

        if "last week" in lowered:
            start = (today - timedelta(days=today.weekday() + 7)).strftime("%Y-%m-%d")
            end = (today - timedelta(days=today.weekday() + 1)).strftime("%Y-%m-%d")
            return TimeRange(start=start, end=end, relative="last_week")

        if "this week" in lowered:
            start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")
            return TimeRange(start=start, end=end, relative="this_week")

        if "last month" in lowered:
            first_this_month = today.replace(day=1)
            last_month_end = first_this_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return TimeRange(
                start=last_month_start.strftime("%Y-%m-%d"),
                end=last_month_end.strftime("%Y-%m-%d"),
                relative="last_month",
            )

        if "this month" in lowered:
            start = today.replace(day=1).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")
            return TimeRange(start=start, end=end, relative="this_month")

        if "last 7 days" in lowered or "past week" in lowered or "past 7" in lowered:
            start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")
            return TimeRange(start=start, end=end, relative="last_7_days")

        if "last 30 days" in lowered or "past month" in lowered or "past 30" in lowered:
            start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
            end = today.strftime("%Y-%m-%d")
            return TimeRange(start=start, end=end, relative="last_30_days")

        # fallback: last 7 days
        start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")
        return TimeRange(start=start, end=end, relative="default_7_days")
