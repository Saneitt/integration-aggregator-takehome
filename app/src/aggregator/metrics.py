from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

http_requests_total = Counter("http_requests_total", "HTTP requests", ["route", "method", "status"])
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds", "HTTP duration", ["route"]
)
token_requests_total = Counter("token_requests_total", "Token request outcomes", ["outcome"])
token_queue_depth = Gauge("token_queue_depth", "Queued token requests")
token_request_duration_seconds = Histogram(
    "token_request_duration_seconds", "Token request duration"
)
openbao_requests_total = Counter("openbao_requests_total", "OpenBao requests", ["op", "status"])
openbao_request_duration_seconds = Histogram(
    "openbao_request_duration_seconds", "OpenBao request duration", ["op"]
)

metrics_app = make_asgi_app()
