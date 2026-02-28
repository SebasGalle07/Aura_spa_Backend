from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "Aura Spa Backend"
    API_V1_STR: str = "/api/v1"

    SECRET_KEY: str = "CHANGE_ME"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    DATABASE_URL: str = "postgresql+psycopg://postgres:CHANGE_ME@localhost:5432/aura_spa"

    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    SEED_ON_STARTUP: bool = True
    AUTO_CREATE_TABLES: bool = False

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def _assemble_cors(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v


settings = Settings()
