from datetime import datetime
from urllib.parse import quote

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.mailer import send_email_verification_email
from app.core.security import create_email_verification_token, decode_token, hash_token
from app.core.time import utc_from_timestamp
from app.crud.token import store_email_verification_token


def _expiry_datetime_from_token(token: str) -> datetime:
    payload = decode_token(token)
    exp = payload.get("exp")
    if exp is None:
        raise HTTPException(status_code=500, detail="Token sin expiracion")
    return utc_from_timestamp(exp)


def build_verify_email_link(token: str) -> str:
    base = settings.FRONTEND_APP_URL.rstrip("/")
    return f"{base}/verify-email?token={quote(token)}"


def ensure_verification_email_available() -> None:
    if not settings.smtp_enabled:
        raise HTTPException(status_code=503, detail="Verificacion por correo no disponible")


def send_verification_email_or_raise(db: Session, user) -> None:
    ensure_verification_email_available()

    token = create_email_verification_token(subject=str(user.id))
    expires_at = _expiry_datetime_from_token(token)

    try:
        send_email_verification_email(user.email, build_verify_email_link(token))
        store_email_verification_token(db, user.id, hash_token(token), expires_at)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="No fue posible enviar el correo de verificacion") from exc
