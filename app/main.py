from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.core.config import settings
from app.db.session import engine
from app.db.base import Base
from app.monitoring import metrics_response, prometheus_http_middleware
import app.models  # noqa: F401
from app.seeds.seed_data import seed_data_if_needed
from app.services.reservation_expirer import start_reservation_expirer, stop_reservation_expirer

media_root = Path(settings.MEDIA_ROOT)
media_root.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json")

origins = settings.BACKEND_CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(prometheus_http_middleware)

app.mount(settings.MEDIA_URL, StaticFiles(directory=str(media_root)), name="media")


@app.on_event("startup")
def on_startup():
    (media_root / "services").mkdir(parents=True, exist_ok=True)
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
    if settings.SEED_ON_STARTUP:
        seed_data_if_needed()
    start_reservation_expirer()


@app.on_event("shutdown")
def on_shutdown():
    stop_reservation_expirer()


@app.get(settings.METRICS_PATH, include_in_schema=False)
def metrics():
    return metrics_response()


@app.get("/healthz", include_in_schema=False)
def healthz():
    return {"ok": True}


app.include_router(api_router, prefix=settings.API_V1_STR)
