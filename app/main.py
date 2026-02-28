from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.db.session import engine
from app.db.base import Base
import app.models  # noqa: F401
from app.seeds.seed_data import seed_data_if_needed


app = FastAPI(title=settings.PROJECT_NAME, openapi_url=f"{settings.API_V1_STR}/openapi.json")

origins = settings.BACKEND_CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
    if settings.SEED_ON_STARTUP:
        seed_data_if_needed()


app.include_router(api_router, prefix=settings.API_V1_STR)
