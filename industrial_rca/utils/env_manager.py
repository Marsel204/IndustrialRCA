"""
Environment and API key manager for Industrial Root Cause Analysis.
Handles persistence of API keys to .env using python-dotenv, runtime environment synchronization,
and dynamic reconfiguration of active LLM clients.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import dotenv
from industrial_rca.config import ROOT_DIR, ENV_FILE
from industrial_rca.tools.deepseek_client import (
    DeepSeekClient,
    reconfigure_all_deepseek_clients,
)

logger = logging.getLogger(__name__)


def get_env_path() -> Path:
    """Returns the canonical Path to the project root .env file."""
    return ENV_FILE


def mask_api_key(key: Optional[str]) -> str:
    """
    Returns a masked representation of an API key for safe UI display.
    Example: sk-1234567890abcdef -> sk-12***cdef
    """
    if not key:
        return ""
    clean = key.strip()
    if len(clean) <= 8:
        return "***"
    return f"{clean[:5]}***{clean[-4:]}"


def get_api_key_status() -> Dict[str, Any]:
    """
    Reads the current API key status from environment and .env file.
    Returns status metadata without exposing the full raw secret.
    """
    env_path = get_env_path()
    raw_key = os.environ.get("DEEPSEEK_API_KEY")

    # If not in os.environ, check .env directly
    if not raw_key and env_path.exists():
        raw_key = dotenv.get_key(str(env_path), "DEEPSEEK_API_KEY")

    has_key = bool(raw_key and raw_key.strip() not in ("mock", "test", "dummy", ""))
    base_url = os.environ.get("DEEPSEEK_BASE_URL") or (
        dotenv.get_key(str(env_path), "DEEPSEEK_BASE_URL") if env_path.exists() else None
    ) or "https://api.deepseek.com/v1"
    
    model = os.environ.get("DEEPSEEK_MODEL") or (
        dotenv.get_key(str(env_path), "DEEPSEEK_MODEL") if env_path.exists() else None
    ) or "deepseek-flash"

    return {
        "has_key": has_key,
        "masked_key": mask_api_key(raw_key) if has_key else "",
        "provider": "DeepSeek",
        "base_url": base_url,
        "model": model,
        "is_live": has_key,
        "status": "ONLINE" if has_key else "SIMULATION",
        "env_path": str(env_path),
        "env_exists": env_path.exists(),
    }


def save_api_key(
    api_key: str,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Persists API key (and optional endpoint/model) into the root .env file,
    updates os.environ, and dynamically reconfigures active DeepSeek client instances.
    """
    clean_key = api_key.strip()
    if not clean_key:
        raise ValueError("API key cannot be empty.")

    env_path = get_env_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    if not env_path.exists():
        env_path.touch()

    # 1. Update .env file via python-dotenv
    dotenv.set_key(str(env_path), "DEEPSEEK_API_KEY", clean_key, quote_mode="never")
    os.environ["DEEPSEEK_API_KEY"] = clean_key

    if base_url:
        clean_url = base_url.strip()
        dotenv.set_key(str(env_path), "DEEPSEEK_BASE_URL", clean_url, quote_mode="never")
        os.environ["DEEPSEEK_BASE_URL"] = clean_url

    if model:
        clean_model = model.strip()
        dotenv.set_key(str(env_path), "DEEPSEEK_MODEL", clean_model, quote_mode="never")
        os.environ["DEEPSEEK_MODEL"] = clean_model

    # 2. Dynamically reconfigure all active in-memory clients
    reconfigure_all_deepseek_clients(
        api_key=clean_key,
        base_url=base_url,
        default_model=model,
    )

    logger.info(f"Updated DEEPSEEK_API_KEY in {env_path} and reconfigured active DeepSeek clients.")

    status = get_api_key_status()
    status["success"] = True
    status["message"] = f"API key saved to {env_path.name} and activated successfully."
    return status


def delete_api_key() -> Dict[str, Any]:
    """
    Removes DEEPSEEK_API_KEY from .env, clears os.environ, and reverts
    all active clients to deterministic simulation mode.
    """
    env_path = get_env_path()
    if env_path.exists():
        dotenv.unset_key(str(env_path), "DEEPSEEK_API_KEY")

    os.environ.pop("DEEPSEEK_API_KEY", None)

    # Reconfigure active clients to mock/simulation mode
    reconfigure_all_deepseek_clients(api_key="")

    logger.info(f"Removed DEEPSEEK_API_KEY from {env_path} and reset clients to simulation mode.")

    status = get_api_key_status()
    status["success"] = True
    status["message"] = "API key removed from .env. System running in deterministic simulation mode."
    return status


def test_api_credentials(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Tests connectivity to DeepSeek API without saving if temporary credentials are provided,
    or tests the currently configured credentials.
    """
    effective_key = api_key.strip() if api_key else os.environ.get("DEEPSEEK_API_KEY")
    if not effective_key:
        return {
            "success": False,
            "status": "FAILED",
            "is_live": False,
            "message": "No API key provided or currently configured.",
        }

    temp_client = DeepSeekClient(
        api_key=effective_key,
        base_url=base_url,
        default_model=model,
    )

    result = temp_client.test_connection()
    success = result.get("status") == "ONLINE" and result.get("is_live", False)
    
    return {
        "success": success,
        "status": result.get("status", "FAILED"),
        "is_live": result.get("is_live", False),
        "model": result.get("model"),
        "response": result.get("response"),
        "message": (
            "Successfully connected to DeepSeek API."
            if success
            else f"Connection failed. Response: {result.get('response', 'Unknown error')}"
        ),
        "usage": result.get("usage", {}),
    }
