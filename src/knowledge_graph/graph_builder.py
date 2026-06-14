from typing import Any, Dict, List, Optional

import pandas as pd

from .knowledge_graph import AdOpsKnowledgeGraph


class GraphBuilder:
    """Builds an AdOpsKnowledgeGraph from campaign / inventory / delivery DataFrames."""

    def build_from_data(
        self,
        campaigns_df: pd.DataFrame,
        inventory_df: pd.DataFrame,
        delivery_df: pd.DataFrame,
    ) -> AdOpsKnowledgeGraph:
        """Construct a populated knowledge graph from sample or real data.

        Args:
            campaigns_df: columns — campaign_id, campaign_name, advertiser, region,
                          device, channel, budget, start_date, end_date, status
            inventory_df: columns — inventory_id, publisher, domain, channel, region,
                          device, format, floor_price, viewability_rate
            delivery_df:  columns — log_id, campaign_id, inventory_id, impressions,
                          clicks, spend, geo, device, fraud_score

        Returns:
            Populated AdOpsKnowledgeGraph instance.
        """
        kg = AdOpsKnowledgeGraph()

        # ── 1. Seed known entity types from raw data ────────────────────────

        self._add_campaigns(kg, campaigns_df)
        self._add_inventory(kg, inventory_df)
        self._add_regions(kg, campaigns_df, inventory_df)
        self._add_devices(kg, campaigns_df, inventory_df)
        self._add_channels(kg, campaigns_df, inventory_df)
        self._add_advertisers(kg, campaigns_df)
        self._add_content_categories(kg, inventory_df)

        # ── 2. Build relationships ──────────────────────────────────────────

        self._link_campaign_targets_region(kg, campaigns_df)
        self._link_campaign_uses_inventory(kg, delivery_df)
        self._link_campaign_has_advertiser(kg, campaigns_df)
        self._link_inventory_belongs_to_channel(kg, inventory_df)
        self._link_inventory_located_in_region(kg, inventory_df)
        self._link_inventory_device_type(kg, inventory_df)

        # ── 3. Detect & attach issues from delivery data ────────────────────

        self._attach_issues(kg, delivery_df, campaigns_df)

        return kg

    # ── private helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _nid(entity_type: str, eid: Any) -> str:
        return f"{entity_type}::{eid}"

    # ── node creators ───────────────────────────────────────────────────────

    def _add_campaigns(self, kg: AdOpsKnowledgeGraph, df: pd.DataFrame) -> None:
        for _, row in df.iterrows():
            kg.add_entity(
                "Campaign",
                str(row["campaign_id"]),
                {
                    "name": row.get("campaign_name", ""),
                    "budget": float(row.get("budget", 0)),
                    "start_date": str(row.get("start_date", "")),
                    "end_date": str(row.get("end_date", "")),
                    "status": row.get("status", "active"),
                },
            )

    def _add_inventory(self, kg: AdOpsKnowledgeGraph, df: pd.DataFrame) -> None:
        for _, row in df.iterrows():
            kg.add_entity(
                "Inventory",
                str(row["inventory_id"]),
                {
                    "publisher": row.get("publisher", ""),
                    "domain": row.get("domain", ""),
                    "format": row.get("format", "display"),
                    "floor_price": float(row.get("floor_price", 0)),
                    "viewability_rate": float(row.get("viewability_rate", 0)),
                },
            )

    def _add_regions(
        self, kg: AdOpsKnowledgeGraph, camp_df: pd.DataFrame, inv_df: pd.DataFrame
    ) -> None:
        regions: set = set()
        for col, src in [("region", camp_df), ("region", inv_df)]:
            if col in src.columns:
                regions.update(str(v) for v in src[col].dropna().unique())
        for r in sorted(regions):
            kg.add_entity("Region", r, {"name": r})

    def _add_devices(
        self, kg: AdOpsKnowledgeGraph, camp_df: pd.DataFrame, inv_df: pd.DataFrame
    ) -> None:
        devices: set = set()
        for col, src in [("device", camp_df), ("device", inv_df)]:
            if col in src.columns:
                devices.update(str(v) for v in src[col].dropna().unique())
        for d in sorted(devices):
            kg.add_entity("Device", d, {"name": d})

    def _add_channels(
        self, kg: AdOpsKnowledgeGraph, camp_df: pd.DataFrame, inv_df: pd.DataFrame
    ) -> None:
        channels: set = set()
        for col, src in [("channel", camp_df), ("channel", inv_df)]:
            if col in src.columns:
                channels.update(str(v) for v in src[col].dropna().unique())
        for c in sorted(channels):
            kg.add_entity("Channel", c, {"name": c})

    def _add_advertisers(self, kg: AdOpsKnowledgeGraph, df: pd.DataFrame) -> None:
        if "advertiser" not in df.columns:
            return
        for adv in df["advertiser"].dropna().unique():
            kg.add_entity("Advertiser", str(adv), {"name": str(adv)})

    def _add_content_categories(self, kg: AdOpsKnowledgeGraph, df: pd.DataFrame) -> None:
        if "content_category" not in df.columns:
            return
        for cat in df["content_category"].dropna().unique():
            kg.add_entity("ContentCategory", str(cat), {"name": str(cat)})

    # ── edge creators ───────────────────────────────────────────────────────

    def _link_campaign_targets_region(
        self, kg: AdOpsKnowledgeGraph, df: pd.DataFrame
    ) -> None:
        if "region" not in df.columns:
            return
        for _, row in df.iterrows():
            src = self._nid("Campaign", row["campaign_id"])
            tgt = self._nid("Region", row["region"])
            if src in kg.graph and tgt in kg.graph:
                kg.add_relationship(
                    src, tgt, "TARGETS",
                    weight=1.0,
                    attributes={"source": "campaign"},
                )

    def _link_campaign_uses_inventory(
        self, kg: AdOpsKnowledgeGraph, df: pd.DataFrame
    ) -> None:
        pairs: Dict[str, set] = {}
        for _, row in df.iterrows():
            cid = self._nid("Campaign", row["campaign_id"])
            iid = self._nid("Inventory", row.get("inventory_id", ""))
            if not iid.endswith("::"):
                pairs.setdefault(cid, set()).add(iid)
        for cid, inv_set in pairs.items():
            for iid in inv_set:
                if cid in kg.graph and iid in kg.graph:
                    kg.add_relationship(cid, iid, "USES", weight=1.0)

    def _link_campaign_has_advertiser(
        self, kg: AdOpsKnowledgeGraph, df: pd.DataFrame
    ) -> None:
        if "advertiser" not in df.columns:
            return
        for _, row in df.iterrows():
            src = self._nid("Campaign", row["campaign_id"])
            tgt = self._nid("Advertiser", row["advertiser"])
            if src in kg.graph and tgt in kg.graph:
                kg.add_relationship(src, tgt, "HAS_ADVERTISER", weight=1.0)

    def _link_inventory_belongs_to_channel(
        self, kg: AdOpsKnowledgeGraph, df: pd.DataFrame
    ) -> None:
        if "channel" not in df.columns:
            return
        for _, row in df.iterrows():
            src = self._nid("Inventory", row["inventory_id"])
            tgt = self._nid("Channel", row["channel"])
            if src in kg.graph and tgt in kg.graph:
                kg.add_relationship(src, tgt, "BELONGS_TO", weight=1.0)

    def _link_inventory_located_in_region(
        self, kg: AdOpsKnowledgeGraph, df: pd.DataFrame
    ) -> None:
        if "region" not in df.columns:
            return
        for _, row in df.iterrows():
            src = self._nid("Inventory", row["inventory_id"])
            tgt = self._nid("Region", row["region"])
            if src in kg.graph and tgt in kg.graph:
                kg.add_relationship(src, tgt, "LOCATED_IN", weight=1.0)

    def _link_inventory_device_type(
        self, kg: AdOpsKnowledgeGraph, df: pd.DataFrame
    ) -> None:
        if "device" not in df.columns:
            return
        for _, row in df.iterrows():
            src = self._nid("Inventory", row["inventory_id"])
            tgt = self._nid("Device", row["device"])
            if src in kg.graph and tgt in kg.graph:
                kg.add_relationship(src, tgt, "DEVICE_TYPE", weight=1.0)

    # ── issue detection ─────────────────────────────────────────────────────

    def _attach_issues(
        self,
        kg: AdOpsKnowledgeGraph,
        delivery_df: pd.DataFrame,
        campaigns_df: pd.DataFrame,
    ) -> None:
        if delivery_df.empty:
            return
        grouped = delivery_df.groupby("campaign_id")
        issue_id = 0
        for cid, group in grouped:
            total_impr = group["impressions"].sum()
            fraud_mean = group["fraud_score"].mean()
            low_view = (group.get("fraud_score", pd.Series([0])) > 0.15).sum()
            total_rows = len(group)

            issues = []
            if fraud_mean > 0.12:
                issues.append(("fraud_signal", "High fraud score detected", fraud_mean))
            if total_impr < 1000 and total_rows > 1:
                issues.append(
                    ("delivery_underperformance", "Low delivery volume", None)
                )
            if low_view > total_rows * 0.3:
                issues.append(
                    ("viewability_drop", "Viewability anomaly across delivery", None)
                )

            for issue_type, desc, score in issues:
                issue_id += 1
                eid = f"ISSUE-{issue_id:03d}"
                attrs: Dict[str, Any] = {
                    "issue_type": issue_type,
                    "description": desc,
                    "campaign_id": cid,
                    "severity": "high" if (score or 0) > 0.15 else "medium",
                }
                if score is not None:
                    attrs["score"] = round(score, 4)
                kg.add_entity("Issue", eid, attrs)
                src = self._nid("Campaign", cid)
                tgt = self._nid("Issue", eid)
                if src in kg.graph and tgt in kg.graph:
                    kg.add_relationship(
                        src, tgt, "HAS_ISSUE", weight=float(attrs["severity"] == "high") or 0.5,
                    )
