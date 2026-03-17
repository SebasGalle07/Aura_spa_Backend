from time import perf_counter

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from app.core.config import settings

HTTP_REQUESTS_TOTAL = Counter(
    "aura_spa_http_requests_total",
    "Total de solicitudes HTTP procesadas por el backend.",
    ("method", "path", "status"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "aura_spa_http_request_duration_seconds",
    "Duracion de solicitudes HTTP en segundos.",
    ("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "aura_spa_http_requests_in_progress",
    "Solicitudes HTTP en curso.",
    ("method", "path"),
)
AUTH_ATTEMPTS_TOTAL = Counter(
    "aura_spa_auth_attempts_total",
    "Intentos de autenticacion por metodo y resultado.",
    ("method", "result"),
)
APPOINTMENT_EVENTS_TOTAL = Counter(
    "aura_spa_appointment_events_total",
    "Eventos relevantes del ciclo de vida de reservas.",
    ("event", "status"),
)
APPOINTMENT_STATUS_TRANSITIONS_TOTAL = Counter(
    "aura_spa_appointment_status_transitions_total",
    "Transiciones de estado de reservas.",
    ("from_status", "to_status"),
)
PAYMENT_EVENTS_TOTAL = Counter(
    "aura_spa_payment_events_total",
    "Eventos de pagos procesados por proveedor y estado.",
    ("provider", "status"),
)


def _label_status(value: str | None) -> str:
    return (value or "none").strip().lower()


def _route_label(request: Request) -> str:
    route = request.scope.get("route")
    path_template = getattr(route, "path", None) or getattr(route, "path_format", None)
    if path_template:
        return str(path_template)
    return request.url.path


async def prometheus_http_middleware(request: Request, call_next):
    if not settings.PROMETHEUS_ENABLED:
        return await call_next(request)

    if request.url.path == settings.METRICS_PATH:
        return await call_next(request)

    method = request.method
    path = _route_label(request)
    start = perf_counter()
    status_code = 500
    HTTP_REQUESTS_IN_PROGRESS.labels(method=method, path=path).inc()

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration = perf_counter() - start
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status=str(status_code)).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path).observe(duration)
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method, path=path).dec()


def metrics_response() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def observe_auth_attempt(method: str, result: str) -> None:
    AUTH_ATTEMPTS_TOTAL.labels(method=method, result=result).inc()


def observe_appointment_event(event: str, status: str) -> None:
    APPOINTMENT_EVENTS_TOTAL.labels(event=event, status=_label_status(status)).inc()


def observe_appointment_transition(from_status: str | None, to_status: str) -> None:
    APPOINTMENT_STATUS_TRANSITIONS_TOTAL.labels(
        from_status=_label_status(from_status),
        to_status=_label_status(to_status),
    ).inc()


def observe_payment_event(provider: str | None, status: str) -> None:
    PAYMENT_EVENTS_TOTAL.labels(
        provider=(provider or "unknown").strip().lower(),
        status=_label_status(status),
    ).inc()
