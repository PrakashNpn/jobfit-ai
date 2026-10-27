"""Structured JSON logs, request IDs, and cost tracking for Claude calls."""

import contextvars
import json
import logging
import sys
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

# USD per million tokens (input, output). Used only for the estimated-cost log field.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "event": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        entry.update(getattr(record, "fields", {}))
        if record.exc_info:
            entry["error"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("jobfit")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False


log = logging.getLogger("jobfit")


def log_event(event: str, **fields) -> None:
    log.info(event, extra={"fields": fields})


def log_claude_usage(operation: str, model: str, usage, started: float) -> None:
    """One log line per Claude call: tokens, latency and estimated cost."""
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    price_in, price_out = PRICES.get(model, (0.0, 0.0))
    log_event(
        "claude_call",
        operation=operation,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=round((time.perf_counter() - started) * 1000),
        est_cost_usd=round(input_tokens * price_in / 1e6 + output_tokens * price_out / 1e6, 6),
    )


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Gives every request an ID (returned as X-Request-ID) and logs one line per request."""

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        token = request_id_var.set(rid)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("request_failed", extra={"fields": {"path": request.url.path}})
            raise
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        log.info(
            "request",
            extra={
                "fields": {
                    "request_id": rid,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000),
                }
            },
        )
        return response
