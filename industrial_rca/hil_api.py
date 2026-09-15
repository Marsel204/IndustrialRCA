"""
Hardware-in-the-Loop (HIL) REST Telemetry & Incident Ingestion API.
Re-exports unified FastAPI application and HIL incident utilities from industrial_rca.api.
"""

from industrial_rca.api import (
    api_app,
    IncidentPayload,
    LATEST_HIL_INCIDENT,
    start_fastapi_background_daemon,
    ingest_incident,
    get_telemetry_health as api_health,
)

__all__ = [
    "api_app",
    "IncidentPayload",
    "LATEST_HIL_INCIDENT",
    "start_fastapi_background_daemon",
    "ingest_incident",
    "api_health",
]
