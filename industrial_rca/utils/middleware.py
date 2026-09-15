"""
FastAPI Middlewares and Exception Handlers for Request Tracing and Observability.
"""

import time
import uuid
import traceback
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from industrial_rca.utils.logging import get_logger, set_trace_context, clear_trace_context

logger = get_logger("industrial_rca.middleware")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures every incoming HTTP request has a unique Request ID.
    Propagates it to response headers and logging context.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Request-ID") or f"req-{uuid.uuid4().hex[:8]}"
        set_trace_context(request_id=req_id)

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            process_time_ms = (time.perf_counter() - start_time) * 1000
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"

            # Log slow requests or all requests when in debug
            if process_time_ms > 1000:
                logger.warning(
                    f"SLOW REQUEST: {request.method} {request.url.path} took {process_time_ms:.1f}ms"
                )
            return response
        except Exception as exc:
            process_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"UNHANDLED EXCEPTION in {request.method} {request.url.path} after {process_time_ms:.1f}ms: {exc}\n"
                f"{traceback.format_exc()}"
            )
            return JSONResponse(
                status_code=500,
                headers={"X-Request-ID": req_id},
                content={
                    "error": "InternalServerError",
                    "message": str(exc),
                    "type": exc.__class__.__name__,
                    "request_id": req_id,
                    "path": request.url.path,
                },
            )
        finally:
            clear_trace_context()
