from urllib.parse import urlsplit

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_ignore_empty=True,
        extra='ignore',
    )

    PROJECT_NAME: str = 'Aura Spa Backend'
    API_V1_STR: str = '/api/v1'

    SECRET_KEY: str = 'CHANGE_ME'
    ALGORITHM: str = 'HS256'
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    RESET_TOKEN_EXPIRE_MINUTES: int = 30
    RETURN_RESET_TOKEN: bool = False

    DATABASE_URL: str = 'postgresql+psycopg://postgres:CHANGE_ME@localhost:5432/aura_spa'

    BACKEND_CORS_ORIGINS: str | list[str] = 'http://localhost:4200'
    FRONTEND_APP_URL: str = 'http://localhost:4200'

    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_FROM_NAME: str = 'Aura Spa'
    SMTP_USE_TLS: bool = True
    GOOGLE_CLIENT_IDS: str | list[str] = ''

    MEDIA_ROOT: str = 'media'
    MEDIA_URL: str = '/media'
    STORAGE_BUCKET: str | None = None
    STORAGE_PREFIX: str = 'branding'

    SEED_ON_STARTUP: bool = True
    AUTO_CREATE_TABLES: bool = False

    @field_validator('BACKEND_CORS_ORIGINS', mode='before')
    @classmethod
    def _assemble_cors(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [i.strip() for i in v.split(',') if i.strip()]
        return v

    @model_validator(mode='after')
    def _finalize_settings(self):
        origins = self.BACKEND_CORS_ORIGINS if isinstance(self.BACKEND_CORS_ORIGINS, list) else []
        frontend_origin = self._normalize_origin(self.FRONTEND_APP_URL)
        if frontend_origin:
            origins.append(frontend_origin)

        seen = set()
        cleaned: list[str] = []
        for origin in origins:
            candidate = self._normalize_origin(origin)
            if candidate and candidate not in seen:
                seen.add(candidate)
                cleaned.append(candidate)
        self.BACKEND_CORS_ORIGINS = cleaned
        self.GOOGLE_CLIENT_IDS = self._normalize_csv(self.GOOGLE_CLIENT_IDS)
        return self

    @staticmethod
    def _normalize_csv(value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(',') if item.strip()]
        return [item.strip() for item in value if item and item.strip()]

    @staticmethod
    def _normalize_origin(url_or_origin: str) -> str:
        value = (url_or_origin or '').strip().rstrip('/')
        if not value:
            return ''
        parsed = urlsplit(value)
        if parsed.scheme and parsed.netloc:
            return f'{parsed.scheme}://{parsed.netloc}'
        return value

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_USERNAME and self.SMTP_PASSWORD and self.SMTP_FROM_EMAIL)

    @property
    def google_login_enabled(self) -> bool:
        return bool(self.GOOGLE_CLIENT_IDS)


settings = Settings()
