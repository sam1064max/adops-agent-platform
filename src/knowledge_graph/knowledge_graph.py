import json
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx


class AdOpsKnowledgeGraph:
    """MultiDiGraph wrapper for AdOps entity-relationship model."""

    def __init__(self) -> None:
        self._graph: nx.MultiDiGraph = nx.MultiDiGraph()

    # ── entity ops ──────────────────────────────────────────────────────────

    def add_entity(
        self, entity_type: str, entity_id: str, attributes: Optional[Dict[str, Any]] = None
    ) -> str:
        node_id = f"{entity_type}::{entity_id}"
        self._graph.add_node(
            node_id,
            type=entity_type,
            id=entity_id,
            **(attributes or {}),
        )
        return node_id

    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        weight: float = 1.0,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._graph.add_edge(
            source_id,
            target_id,
            key=rel_type,
            relationship=rel_type,
            weight=weight,
            **(attributes or {}),
        )

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        if entity_id not in self._graph:
            return None
        return dict(self._graph.nodes[entity_id])

    def get_relationships(
        self, entity_id: str
    ) -> List[Tuple[str, str, float]]:
        if entity_id not in self._graph:
            return []
        results: List[Tuple[str, str, float]] = []
        for _, target, data in self._graph.out_edges(entity_id, data=True):
            results.append((target, data.get("relationship", ""), data.get("weight", 1.0)))
        return results

    # ── graph traversal ─────────────────────────────────────────────────────

    def find_path(self, source_id: str, target_id: str) -> Optional[List[str]]:
        try:
            return nx.shortest_path(self._graph, source=source_id, target=target_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def find_connected_entities(
        self, entity_id: str, rel_type: Optional[str] = None
    ) -> List[str]:
        if entity_id not in self._graph:
            return []
        if rel_type is None:
            return list(nx.node_connected_component(self._graph.to_undirected(), entity_id))
        neighbors = []
        for _, target, data in self._graph.out_edges(entity_id, data=True):
            if data.get("relationship") == rel_type:
                neighbors.append(target)
        return neighbors

    # ── subgraph ────────────────────────────────────────────────────────────

    def get_subgraph(self, entity_types: List[str]) -> "AdOpsKnowledgeGraph":
        sub = AdOpsKnowledgeGraph()
        for node, data in self._graph.nodes(data=True):
            if data.get("type") in entity_types:
                sub._graph.add_node(node, **dict(data))
        for u, v, key, data in self._graph.edges(keys=True, data=True):
            if u in sub._graph and v in sub._graph:
                sub._graph.add_edge(u, v, key=key, **dict(data))
        return sub

    # ── counts & impact ─────────────────────────────────────────────────────

    def get_entity_count(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for _, data in self._graph.nodes(data=True):
            t = data.get("type", "unknown")
            counts[t] = counts.get(t, 0) + 1
        return counts

    def get_impact_chain(self, campaign_id: str) -> List[Dict[str, Any]]:
        if campaign_id not in self._graph:
            return []
        affected = []
        visited = {campaign_id}
        queue = [campaign_id]
        while queue:
            current = queue.pop(0)
            for _, target, data in self._graph.out_edges(current, data=True):
                if target not in visited:
                    visited.add(target)
                    node_data = dict(self._graph.nodes[target])
                    node_data["_source"] = current
                    node_data["_relationship"] = data.get("relationship", "")
                    affected.append(node_data)
                    queue.append(target)
        return affected

    # ── serialization ───────────────────────────────────────────────────────

    def to_json(self) -> str:
        payload = {
            "nodes": [
                {"_nid": n, **dict(d)}
                for n, d in self._graph.nodes(data=True)
            ],
            "edges": [
                {
                    "_source": u,
                    "_target": v,
                    "_key": k,
                    **dict(d),
                }
                for u, v, k, d in self._graph.edges(keys=True, data=True)
            ],
        }
        return json.dumps(payload, indent=2, default=str)

    @classmethod
    def from_json(cls, data: str) -> "AdOpsKnowledgeGraph":
        kg = cls()
        payload = json.loads(data)
        for n in payload.get("nodes", []):
            nid = n.pop("_nid")
            kg._graph.add_node(nid, **n)
        for e in payload.get("edges", []):
            u = e.pop("_source")
            v = e.pop("_target")
            k = e.pop("_key")
            kg._graph.add_edge(u, v, key=k, **e)
        return kg

    @property
    def graph(self) -> nx.MultiDiGraph:
        return self._graph
