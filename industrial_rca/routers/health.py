"""
Health and system status endpoints.
"""

import time
from fastapi import APIRouter
from industrial_rca.tools.telemetry_analytics import GLOBAL_TELEMETRY_CACHE
from industrial_rca.routers.common import (
    ensure_default_scenarios,
    SCENARIOS_REGISTRY,
    LATEST_HIL_INCIDENT,
)

router = APIRouter(tags=["Health & Status"])


@router.get("/health")
@router.get("/api/v1/health")
def get_health():
    ensure_default_scenarios()
    cache_stats = GLOBAL_TELEMETRY_CACHE.get_stats()
    return {
        "status": "ONLINE",
        "service": "Industrial RCA Unified Backend API",
        "timestamp": time.time(),
        "time_utc": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "active_scenarios": list(SCENARIOS_REGISTRY.keys()),
        "telemetry_cache": cache_stats,
        "latest_hil_incident": LATEST_HIL_INCIDENT.get("incident_data"),
        "hil_status": LATEST_HIL_INCIDENT.get("pipeline_status"),
    }


@router.get("/api/v1/telemetry/health")
def get_telemetry_health():
    """Backward compatibility endpoint for test suite and HIL simulator."""
    return {
        "status": "ONLINE",
        "service": "Industrial RCA Ingestion Middleware",
        "timestamp": time.time(),
        "latest_incident": LATEST_HIL_INCIDENT.get("incident_data"),
        "pipeline_status": LATEST_HIL_INCIDENT.get("pipeline_status"),
    }
