from typing import Any, Dict, List

from .knowledge_graph import AdOpsKnowledgeGraph


class GraphQueryEngine:
    """Query engine over AdOpsKnowledgeGraph for inventory, campaign, and issue analysis."""

    def __init__(self, kg: AdOpsKnowledgeGraph) -> None:
        self._kg = kg

    # ── inventory queries ───────────────────────────────────────────────────

    def find_affected_inventory(self, campaign_id: str) -> List[Dict[str, Any]]:
        """Return all inventory nodes reachable via USES from a campaign."""
        nid = f"Campaign::{campaign_id}"
        if nid not in self._kg.graph:
            return []
        results = []
        for _, target, data in self._kg.graph.out_edges(nid, data=True):
            if data.get("relationship") == "USES":
                node = self._kg.get_entity(target)
                if node:
                    results.append(node)
        return results

    def find_related_campaigns(self, inventory_id: str) -> List[Dict[str, Any]]:
        """Return all campaign nodes that USES a given inventory."""
        nid = f"Inventory::{inventory_id}"
        if nid not in self._kg.graph:
            return []
        results = []
        for source, _, data in self._kg.graph.in_edges(nid, data=True):
            if data.get("relationship") == "USES":
                node = self._kg.get_entity(source)
                if node:
                    results.append(node)
        return results

    # ── regional / channel queries ──────────────────────────────────────────

    def find_regional_issues(self, region: str) -> List[Dict[str, Any]]:
        """Return all entities (inventory, campaigns, issues) linked to a region."""
        region_nid = f"Region::{region}"
        if region_nid not in self._kg.graph:
            return []
        results = []
        # inbound edges: inventory LOCATED_IN region, campaign TARGETS region
        for source, _, data in self._kg.graph.in_edges(region_nid, data=True):
            node = self._kg.get_entity(source)
            if node:
                node["_via"] = data.get("relationship", "")
                results.append(node)
        # also gather issues attached to campaigns in this region
        for src, _, _ in self._kg.graph.in_edges(region_nid, data=True):
            if src.startswith("Campaign::"):
                for _, tgt, data in self._kg.graph.out_edges(src, data=True):
                    if data.get("relationship") == "HAS_ISSUE":
                        node = self._kg.get_entity(tgt)
                        if node:
                            node["_via"] = "campaign_issue"
                            results.append(node)
        return results

    def find_channel_issues(self, channel: str) -> List[Dict[str, Any]]:
        """Return all entities (inventory, campaigns, issues) on a given channel."""
        channel_nid = f"Channel::{channel}"
        if channel_nid not in self._kg.graph:
            return []
        results = []
        # inbound: inventory BELONGS_TO channel
        for source, _, data in self._kg.graph.in_edges(channel_nid, data=True):
            node = self._kg.get_entity(source)
            if node:
                node["_via"] = data.get("relationship", "")
                results.append(node)
            # walk back to campaigns that USES this inventory
            if source.startswith("Inventory::"):
                for src2, _, data2 in self._kg.graph.in_edges(source, data=True):
                    if data2.get("relationship") == "USES":
                        camp_node = self._kg.get_entity(src2)
                        if camp_node:
                            camp_node["_via"] = "USES"
                            results.append(camp_node)
                        # collect issues on those campaigns
                        for _, tgt, data3 in self._kg.graph.out_edges(src2, data=True):
                            if data3.get("relationship") == "HAS_ISSUE":
                                issue_node = self._kg.get_entity(tgt)
                                if issue_node:
                                    issue_node["_via"] = "campaign_issue"
                                    results.append(issue_node)
        return results

    # ── impact analysis ─────────────────────────────────────────────────────

    def trace_impact(self, issue_entity_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """Given an Issue node id, return affected entities grouped by type."""
        nid = f"Issue::{issue_entity_id}" if not issue_entity_id.startswith("Issue::") else issue_entity_id
        if nid not in self._kg.graph:
            return {}
        affected: Dict[str, List[Dict[str, Any]]] = {}
        # walk backwards to the campaign that HAS_ISSUE
        for source, _, data in self._kg.graph.in_edges(nid, data=True):
            if data.get("relationship") == "HAS_ISSUE":
                camp = self._kg.get_entity(source)
                if camp:
                    affected.setdefault("Campaign", []).append(camp)
                # walk forward from campaign: inventory, region, channel, device, advertiser
                for _, tgt, data2 in self._kg.graph.out_edges(source, data=True):
                    rt = data2.get("relationship", "")
                    node = self._kg.get_entity(tgt)
                    if node:
                        ttype = node.get("type", "unknown")
                        affected.setdefault(ttype, []).append(node)
                    # one more hop from inventory
                    if rt == "USES":
                        for _, tgt2, data3 in self._kg.graph.out_edges(tgt, data=True):
                            r2 = data3.get("relationship", "")
                            node2 = self._kg.get_entity(tgt2)
                            if node2 and r2 in ("BELONGS_TO", "LOCATED_IN", "DEVICE_TYPE"):
                                ttype = node2.get("type", "unknown")
                                affected.setdefault(ttype, []).append(node2)
        return affected

    def get_campaign_footprint(self, campaign_id: str) -> Dict[str, List[str]]:
        """Return the regions, devices, and channels a campaign touches."""
        nid = f"Campaign::{campaign_id}"
        if nid not in self._kg.graph:
            return {"regions": [], "devices": [], "channels": []}
        regions: set = set()
        devices: set = set()
        channels: set = set()

        # direct TARGETS edges -> regions
        for _, tgt, data in self._kg.graph.out_edges(nid, data=True):
            if data.get("relationship") == "TARGETS":
                node = self._kg.get_entity(tgt)
                if node:
                    regions.add(node.get("id", ""))
            # USES -> inventory -> LOCATED_IN / DEVICE_TYPE / BELONGS_TO
            if data.get("relationship") == "USES":
                for _, tgt2, data2 in self._kg.graph.out_edges(tgt, data=True):
                    r2 = data2.get("relationship", "")
                    node2 = self._kg.get_entity(tgt2)
                    if node2:
                        if r2 == "LOCATED_IN":
                            regions.add(node2.get("id", ""))
                        elif r2 == "DEVICE_TYPE":
                            devices.add(node2.get("id", ""))
                        elif r2 == "BELONGS_TO":
                            channels.add(node2.get("id", ""))

        return {
            "regions": sorted(regions),
            "devices": sorted(devices),
            "channels": sorted(channels),
        }
