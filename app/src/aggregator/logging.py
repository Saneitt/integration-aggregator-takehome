import contextvars
import json
import logging
import re
import time
from datetime import UTC, datetime

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from aggregator.metrics import http_request_duration_seconds, http_requests_total

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
SECRET_PATTERNS = re.compile(
    r"(?i)(?:gh[opsu]_[A-Za-z0-9_]{20,}|glpat-[A-Za-z0-9_-]{20,}|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_.-]+)"
)


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        record.msg = SECRET_PATTERNS.sub("[REDACTED]", message)
        record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for field in ("method", "route", "status", "duration_ms"):
            value = getattr(record, field, None)
            if value is not None:
                data[field] = getattr(value, "path", value)
        return json.dumps(data, separators=(",", ":"))


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        import uuid

        if b"%2f" in request.scope.get("raw_path", b"").lower():
            return JSONResponse(
                status_code=422,
                media_type="application/problem+json",
                content={
                    "type": "about:blank",
                    "title": "Invalid input",
                    "status": 422,
                    "detail": "Encoded path separators are not allowed.",
                    "code": "validation_error",
                },
            )

        request_id = uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            route = request.scope.get("route")
            route_name = getattr(route, "path", "unmatched")
            http_requests_total.labels(
                route=route_name, method=request.method, status=str(response.status_code)
            ).inc()
            http_request_duration_seconds.labels(route=route_name).observe(
                time.perf_counter() - started
            )
            logging.getLogger("aggregator.access").info(
                "request",
                extra={
                    "method": request.method,
                    "route": route_name,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            return response
        finally:
            request_id_var.reset(token)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
