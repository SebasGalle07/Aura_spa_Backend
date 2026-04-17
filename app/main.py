from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import engine
from app.db.base import Base
from app.monitoring import metrics_response, prometheus_http_middleware
import app.models  # noqa: F401
from app.seeds.seed_data import seed_data_if_needed
from app.services.reservation_expirer import start_reservation_expirer, stop_reservation_expirer

media_root = Path(settings.MEDIA_ROOT)
media_root.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    (media_root / "services").mkdir(parents=True, exist_ok=True)
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
    if settings.SEED_ON_STARTUP:
        seed_data_if_needed()
    start_reservation_expirer()
    try:
        yield
    finally:
        stop_reservation_expirer()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

origins = settings.BACKEND_CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(prometheus_http_middleware)


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}


@app.get(f"{settings.API_V1_STR}/healthz", include_in_schema=False)
def api_healthz():
    return {"ok": True}


app.mount(settings.MEDIA_URL, StaticFiles(directory=str(media_root)), name="media")

@app.get(settings.METRICS_PATH, include_in_schema=False)
def metrics(
    x_metrics_token: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    provided_token = x_metrics_token
    if not provided_token and authorization and authorization.lower().startswith("bearer "):
        provided_token = authorization.split(" ", 1)[1].strip()
    if settings.METRICS_TOKEN and provided_token != settings.METRICS_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid metrics token")
    return metrics_response()


app.include_router(api_router, prefix=settings.API_V1_STR)
