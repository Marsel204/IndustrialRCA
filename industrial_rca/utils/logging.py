"""
Centralized structured logging utility for the Industrial RCA system.
Provides context-aware logging (correlation IDs, thread IDs, incident IDs)
and standardized formatting for rapid debugging.
"""

import os
import sys
import logging
import contextvars
from typing import Dict, Any, Optional

# Context variable to hold request/execution tracing context
_LOG_CONTEXT: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    "rca_log_context", default={}
)


def set_trace_context(**kwargs):
    """Sets contextual key-values (e.g. request_id, thread_id, asset_id) for current async task or thread."""
    ctx = dict(_LOG_CONTEXT.get())
    ctx.update(kwargs)
    _LOG_CONTEXT.set(ctx)


def clear_trace_context():
    """Resets logging trace context."""
    _LOG_CONTEXT.set({})


def get_trace_context() -> Dict[str, Any]:
    """Returns current logging trace context."""
    return _LOG_CONTEXT.get()


class ContextAwareFormatter(logging.Formatter):
    """Logging formatter that injects correlation ID and contextual metadata."""

    def format(self, record: logging.LogRecord) -> str:
        ctx = _LOG_CONTEXT.get()
        context_parts = []
        if "request_id" in ctx:
            context_parts.append(f"req:{ctx['request_id'][:8]}")
        if "thread_id" in ctx:
            context_parts.append(f"thread:{ctx['thread_id']}")
        if "incident_id" in ctx:
            context_parts.append(f"inc:{ctx['incident_id']}")

        record.trace_context = f"[{' '.join(context_parts)}] " if context_parts else ""
        return super().format(record)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Returns a configured logger with standard formatting and level.
    Usage:
        logger = get_logger(__name__)
        logger.info("Processing telemetry...")
    """
    logger = logging.getLogger(name or "industrial_rca")

    # If handlers already configured, don't duplicate
    if logger.handlers:
        return logger

    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    if os.getenv("RCA_DEBUG", "0") == "1":
        log_level_str = "DEBUG"

    level = getattr(logging, log_level_str, logging.INFO)
    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    fmt = "%(asctime)s | %(levelname)-7s | %(trace_context)s%(name)s:%(lineno)d - %(message)s"
    formatter = ContextAwareFormatter(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False
    return logger
