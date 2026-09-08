"""
Asset Topology Tracer based on ISA-95 Equipment Hierarchy.
Performs upstream and downstream directed graph traversal and causal chain correlation.
"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional

from industrial_rca.config import TOPOLOGY_FILE


class AssetTopologyTracer:
    """Traverses ISA-95 asset topology graph and correlates cross-asset telemetry anomalies."""

    def __init__(self, topology_path: Optional[Path] = None):
        path = topology_path or TOPOLOGY_FILE
        with open(path, "r", encoding="utf-8") as f:
            self.raw_data = json.load(f)

        self.hierarchy = self.raw_data.get("isa95_hierarchy", {})
        self.equipment = {node["id"]: node for node in self.raw_data.get("equipment_nodes", [])}
        self.edges = self.raw_data.get("topology_edges", [])

        # Build adjacency maps
        self.upstream_map: Dict[str, List[Dict[str, Any]]] = {}   # node -> list of upstream incoming edges
        self.downstream_map: Dict[str, List[Dict[str, Any]]] = {} # node -> list of downstream outgoing edges

        for edge in self.edges:
            src = edge["source"]
            tgt = edge["target"]
            if tgt not in self.upstream_map:
                self.upstream_map[tgt] = []
            self.upstream_map[tgt].append({"node": src, "relation": edge["relation"], "medium": edge.get("medium", "")})

            if src not in self.downstream_map:
                self.downstream_map[src] = []
            self.downstream_map[src].append({"node": tgt, "relation": edge["relation"], "medium": edge.get("medium", "")})

    def get_equipment(self, asset_id: str) -> Optional[Dict[str, Any]]:
        return self.equipment.get(asset_id)

    def get_equipment_sensors(self, asset_id: str) -> List[Dict[str, Any]]:
        node = self.equipment.get(asset_id)
        if not node:
            return []
        return node.get("sensors", [])

    def trace_upstream(self, start_asset_id: str, max_depth: int = 5) -> List[Dict[str, Any]]:
        """
        Traverse upstream across process flow to identify all upstream equipment and associated sensors.
        Returns ordered list from immediate upstream to furthest upstream.
        """
        visited = set()
        queue = [(start_asset_id, 0)]
        upstream_chain = []

        while queue:
            curr_id, depth = queue.pop(0)
            if curr_id in visited or depth >= max_depth:
                continue
            visited.add(curr_id)

            incoming = self.upstream_map.get(curr_id, [])
            for inc in incoming:
                up_node_id = inc["node"]
                if up_node_id not in visited:
                    up_node = self.equipment.get(up_node_id, {})
                    upstream_chain.append({
                        "asset_id": up_node_id,
                        "name": up_node.get("name", up_node_id),
                        "type": up_node.get("type", "Unknown"),
                        "depth": depth + 1,
                        "relation": inc["relation"],
                        "sensors": up_node.get("sensors", []),
                        "operating_specs": up_node.get("operating_specs", {}),
                    })
                    queue.append((up_node_id, depth + 1))

        return upstream_chain

    def trace_downstream(self, start_asset_id: str, max_depth: int = 5) -> List[Dict[str, Any]]:
        """Traverse downstream across process flow."""
        visited = set()
        queue = [(start_asset_id, 0)]
        downstream_chain = []

        while queue:
            curr_id, depth = queue.pop(0)
            if curr_id in visited or depth >= max_depth:
                continue
            visited.add(curr_id)

            outgoing = self.downstream_map.get(curr_id, [])
            for out in outgoing:
                dn_node_id = out["node"]
                if dn_node_id not in visited:
                    dn_node = self.equipment.get(dn_node_id, {})
                    downstream_chain.append({
                        "asset_id": dn_node_id,
                        "name": dn_node.get("name", dn_node_id),
                        "type": dn_node.get("type", "Unknown"),
                        "depth": depth + 1,
                        "relation": out["relation"],
                        "sensors": dn_node.get("sensors", []),
                    })
                    queue.append((dn_node_id, depth + 1))

        return downstream_chain

    def find_earliest_upstream_anomaly(
        self,
        asset_id: str,
        detected_anomalies: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Cross-references detected change-point anomalies with upstream asset topology.
        Determines which upstream asset first exhibited abnormal behavior (the root physical origin).
        """
        upstream_assets = self.trace_upstream(asset_id)
        # Map sensor tags to asset
        sensor_to_asset = {}
        for tag_info in self.get_equipment_sensors(asset_id):
            sensor_to_asset[tag_info["tag"]] = asset_id

        for up in upstream_assets:
            for tag_info in up["sensors"]:
                sensor_to_asset[tag_info["tag"]] = up["asset_id"]

        matched = []
        for anomaly in detected_anomalies:
            tag = anomaly.get("tag")
            if tag in sensor_to_asset:
                matched.append({
                    "tag": tag,
                    "asset_id": sensor_to_asset[tag],
                    "timestamp_sec": anomaly.get("timestamp_sec", 0),
                    "score": anomaly.get("score", 0.0),
                    "details": anomaly,
                })

        if not matched:
            return None

        # Sort by timestamp ascending (earliest first)
        matched.sort(key=lambda x: x["timestamp_sec"])
        return matched[0]
