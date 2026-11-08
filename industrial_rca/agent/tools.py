"""Schema-based read-only tools scoped to one dataset and its asset topology."""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd
from pydantic import BaseModel

from industrial_rca.agent.contracts import (
    Diagnosis,
    MaintenanceQuery,
    ReferenceQuery,
    TelemetryQuery,
    TopologyQuery,
)
from industrial_rca.data.oem_manuals import (
    FMEA_KNOWLEDGE_BASE,
    get_oem_spec,
    get_vfd_fault_info,
)
from industrial_rca.data.telemetry_generator import TelemetryStore
from industrial_rca.tools.cmms_connector import CMMSConnector
from industrial_rca.tools.telemetry_analytics import (
    ChangePointDetector,
    StatisticalProfiler,
)
from industrial_rca.tools.topology_tracer import AssetTopologyTracer


@dataclass(frozen=True)
class Tool:
    description: str
    arguments: type[BaseModel]
    handler: Callable
    source: str


class InvestigationTools:
    def __init__(self, dataset_id: str, asset_id: str):
        self.dataset_id = dataset_id
        self.asset_id = asset_id
        self.dataset = TelemetryStore.get(dataset_id)
        self.topology = AssetTopologyTracer()
        self.allowed_assets = {asset_id}
        self.allowed_assets.update(
            node["asset_id"] for node in self.topology.trace_upstream(asset_id)
        )
        self.allowed_assets.update(
            node["asset_id"] for node in self.topology.trace_downstream(asset_id)
        )
        self.measurement_source = (
            "simulated" if self.dataset.metadata.get("is_simulated") else "measured"
        )
        self.registry = {
            "profile_telemetry": Tool(
                "Compute statistics over an observed channel and sample-index window. Missing channels are unavailable, never zero.",
                TelemetryQuery,
                self.profile,
                self.measurement_source,
            ),
            "detect_change_points": Tool(
                "Find changes in an observed channel. Times are sample indices unless acquisition timing is supplied.",
                TelemetryQuery,
                self.changepoints,
                self.measurement_source,
            ),
            "trace_topology": Tool(
                "Read configured upstream/downstream relationships. Connectivity alone does not prove causation or current component condition.",
                TopologyQuery,
                self.trace,
                "configured",
            ),
            "lookup_oem": Tool(
                "Retrieve OEM/FMEA reference information; possible causes are not observed findings.",
                ReferenceQuery,
                self.oem,
                "reference",
            ),
            "lookup_maintenance": Tool(
                "Retrieve maintenance records. This prototype has simulation fixtures only; real incidents report unavailable.",
                MaintenanceQuery,
                self.maintenance,
                "simulated"
                if self.dataset.metadata.get("is_simulated")
                else "unavailable",
            ),
        }

    @property
    def schemas(self):
        entries = [
            (name, tool.description, tool.arguments)
            for name, tool in self.registry.items()
        ]
        entries.append(
            (
                "submit_diagnosis",
                "Submit an evidence-linked conclusion for review, or explain why the investigation is inconclusive. Cite observation IDs returned by tools. Never force five causal steps.",
                Diagnosis,
            )
        )
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": description,
                    "parameters": schema.model_json_schema(),
                },
            }
            for name, description, schema in entries
        ]

    def require_asset(self, asset_id):
        if asset_id not in self.allowed_assets:
            raise ValueError("Asset is outside this incident's configured topology")

    def series(self, query: TelemetryQuery):
        frame = self.dataset.df_1hz
        if query.tag not in frame or query.tag in {"timestamp", "timestamp_sec"}:
            raise ValueError(f"Measured channel unavailable: {query.tag}")
        end = query.end_index if query.end_index is not None else len(frame)
        if query.start_index >= len(frame) or end > len(frame):
            raise ValueError("Requested sample window is outside the available dataset")
        values = pd.to_numeric(
            frame[query.tag].iloc[query.start_index : end], errors="coerce"
        ).to_numpy(dtype=float)
        if not len(values) or not np.isfinite(values).all():
            raise ValueError(
                "Requested channel/window contains missing or nonfinite readings; collect valid measurements"
            )
        return values, end

    def profile(self, query):
        values, end = self.series(query)
        return {
            **StatisticalProfiler.profile(values),
            "tag": query.tag,
            "sample_count": len(values),
            "start_index": query.start_index,
            "end_index": end,
            "time_basis": "sample_index",
        }

    def changepoints(self, query):
        values, end = self.series(query)
        changes = ChangePointDetector.detect_change_points(values)
        return {
            "tag": query.tag,
            "start_index": query.start_index,
            "end_index": end,
            "time_basis": "sample_index",
            "changes": changes,
        }

    def trace(self, query):
        self.require_asset(query.asset_id)
        traverse = {
            "upstream": self.topology.trace_upstream,
            "downstream": self.topology.trace_downstream,
        }[query.direction]
        return {
            "asset": self.topology.get_equipment(query.asset_id),
            "relationships": traverse(query.asset_id, max_depth=query.max_depth),
        }

    def oem(self, query):
        self.require_asset(query.asset_id)
        spec = get_oem_spec(query.asset_id)
        return {
            "specification": spec,
            "fault_reference": get_vfd_fault_info(query.fault_code)
            if query.fault_code is not None
            else None,
            "candidate_failure_modes": FMEA_KNOWLEDGE_BASE,
            "notice": "Reference knowledge only; not proof of current asset condition.",
        }

    def maintenance(self, query):
        self.require_asset(query.asset_id)
        if not self.dataset.metadata.get("is_simulated"):
            raise ValueError(
                "No live CMMS integration is configured; maintenance history is unavailable"
            )
        return {
            "records": CMMSConnector().query_maintenance_history(query.asset_id),
            "notice": "Simulation fixtures, not live maintenance findings.",
        }
