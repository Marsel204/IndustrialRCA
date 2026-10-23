"""Convert reported incidents into datasets without manufacturing observations."""

from copy import deepcopy
from datetime import UTC, datetime
from uuid import uuid4

import numpy as np
import pandas as pd

from industrial_rca.data.oem_manuals import get_vfd_fault_info
from industrial_rca.data.telemetry_generator import TelemetryDataset


def build_incident_dataset(incident, *, simulated=False):
    incident_id = (
        incident.incident_id or f"INC-{'SIM' if simulated else 'HIL'}-{uuid4().hex}"
    )
    description = (
        incident.fault_description
        or get_vfd_fault_info(incident.fault_code)["description"]
    )
    frame = pd.DataFrame(deepcopy(incident.pre_fault_telemetry))
    # Preserve acquisition order and timestamps. Sample indices are only a separate
    # coordinate for the existing analytics, not claimed acquisition times.
    if "timestamp_sec" not in frame and not frame.empty:
        frame["timestamp_sec"] = np.arange(len(frame))
    return TelemetryDataset(
        scenario_name=f"{'Simulated' if simulated else 'Hardware'} Incident: {description}",
        df_1hz=frame,
        metadata={
            "incident_id": incident_id,
            "asset_id": incident.asset_id,
            "fault_code": incident.fault_code,
            "fault_description": description,
            "condition": "SIMULATED_INCIDENT" if simulated else "HARDWARE_FAULT_TRIP",
            "is_simulated": simulated,
            "source_type": "simulated" if simulated else "measured",
            "anomaly_expected": bool(incident.fault_code),
            "trip_timestamp_sec": None,
            "trip_time_str": "Not supplied",
            "received_at": datetime.now(UTC).isoformat(),
        },
        normal_waveform={},
        fault_waveform={},
    )
