"""
Graph Debugging, State Snapshots, and Replay Utilities for Industrial RCA.

Provides:
- Automatic state snapshot dumping to disk on node execution or failure
- Replay helper to load saved state for isolated unit testing & bug reproduction
- Node execution timing and exception tracing decorator
"""

import os
import sys
import json
import time
import functools
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from industrial_rca.utils.logging import get_logger

logger = get_logger("industrial_rca.graph.debugger")

DEBUG_DIR = Path(".rca_debug")


def _sanitize_for_json(obj: Any) -> Any:
    """Converts numpy arrays, pandas series/dfs, and custom objects to JSON-serializable structures."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_sanitize_for_json(v) for v in obj]
    if hasattr(obj, "to_dict"):
        try:
            return _sanitize_for_json(obj.to_dict())
        except Exception:
            pass
    if hasattr(obj, "tolist"):
        try:
            return obj.tolist()
        except Exception:
            pass
    return str(obj)


def dump_node_state(
    node_name: str,
    state_data: Any,
    output_data: Optional[Any] = None,
    thread_id: Optional[str] = None,
    is_error: bool = False,
    error_msg: Optional[str] = None,
) -> Optional[Path]:
    """
    Saves state snapshot to .rca_debug/{thread_id}/step_{node_name}.json.
    Returns the Path to the saved file or None if writing fails.
    """
    try:
        tid = thread_id or "latest"
        run_dir = DEBUG_DIR / "runs" / tid
        run_dir.mkdir(parents=True, exist_ok=True)

        prefix = "ERR_" if is_error else "STEP_"
        ts = int(time.time() * 1000)
        filename = f"{prefix}{ts}_{node_name}.json"
        target = run_dir / filename

        payload = {
            "node_name": node_name,
            "thread_id": tid,
            "timestamp": time.time(),
            "timestamp_str": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "is_error": is_error,
            "error_msg": error_msg,
            "input_state": _sanitize_for_json(state_data),
            "output_state": _sanitize_for_json(output_data) if output_data is not None else None,
        }

        with open(target, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        if is_error:
            logger.error(f"[DEBUG DUMP] Saved failure snapshot for node '{node_name}' -> {target}")
        elif os.getenv("RCA_DEBUG_DUMP", "0") == "1":
            logger.debug(f"[DEBUG DUMP] Saved state snapshot for node '{node_name}' -> {target}")

        return target
    except Exception as e:
        logger.warning(f"Failed to dump debug state for node '{node_name}': {e}")
        return None


def load_node_state(filepath: str | Path) -> Dict[str, Any]:
    """
    Loads saved state snapshot from file for reproduction or offline inspection.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"State snapshot not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def debug_node(node_name: str) -> Callable:
    """
    Decorator for LangGraph node functions.
    Logs execution start/stop, measures execution time, captures unhandled exceptions,
    and dumps state snapshots on failure or when RCA_DEBUG_DUMP=1.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(state: Any, *args, **kwargs) -> Any:
            thread_id = None
            if isinstance(state, dict):
                thread_id = state.get("incident_id") or state.get("asset_id")

            start_t = time.perf_counter()
            logger.info(f"[{node_name}] Executing node...")

            try:
                result = func(state, *args, **kwargs)
                elapsed_ms = (time.perf_counter() - start_t) * 1000
                logger.info(f"[{node_name}] Completed in {elapsed_ms:.1f}ms")

                if os.getenv("RCA_DEBUG_DUMP", "0") == "1":
                    dump_node_state(node_name, state, output_data=result, thread_id=thread_id)

                return result
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - start_t) * 1000
                err_detail = f"{type(exc).__name__}: {str(exc)}\n{traceback.format_exc()}"
                logger.error(f"[{node_name}] FAILED after {elapsed_ms:.1f}ms: {exc}")

                # Always dump state on failure for debugging
                dump_node_state(
                    node_name=node_name,
                    state_data=state,
                    output_data=None,
                    thread_id=thread_id,
                    is_error=True,
                    error_msg=err_detail,
                )
                raise exc

        return wrapper
    return decorator
