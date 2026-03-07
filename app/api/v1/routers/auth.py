from datetime import datetime
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_token,
    validate_password_length,
)
from app.crud.token import (
    get_refresh_token,
    revoke_refresh_token,
    store_refresh_token,
)
from app.crud.user import authenticate_user, create_user, get_user_by_email, get_user_by_id
from app.db.deps import get_db
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    Token,
)
from app.schemas.user import UserRegister, UserOut

router = APIRouter()
logger = logging.getLogger(__name__)


def _expiry_datetime_from_token(token: str) -> datetime:
    payload = decode_token(token)
    exp = payload.get("exp")
    if exp is None:
        raise HTTPException(status_code=500, detail="Token without expiry")
    return datetime.utcfromtimestamp(exp)


def _issue_session_tokens(db: Session, user) -> dict:
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))
    refresh_expiry = _expiry_datetime_from_token(refresh_token)
    store_refresh_token(db, user.id, hash_token(refresh_token), refresh_expiry)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/register", response_model=Token)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    validate_password_length(user_in.password)
    if get_user_by_email(db, user_in.email):
        logger.warning("Registro rechazado por email duplicado: %s", user_in.email)
        raise HTTPException(status_code=400, detail="Email already registered")
    user = create_user(db, user_in, role="client")
    logger.info("Usuario registrado: id=%s email=%s", user.id, user.email)
    return _issue_session_tokens(db, user)


@router.post("/login", response_model=Token)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    validate_password_length(data.password)
    user = authenticate_user(db, data.email, data.password)
    if not user:
        logger.warning("Login fallido para email=%s", data.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    logger.info("Login exitoso: id=%s email=%s", user.id, user.email)
    return _issue_session_tokens(db, user)


@router.post("/refresh", response_model=Token)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token",
    )
    try:
        token_payload = decode_token(payload.refresh_token)
    except JWTError:
        raise credentials_exception

    if token_payload.get("type") != "refresh":
        raise credentials_exception

    token_hash = hash_token(payload.refresh_token)
    stored_token = get_refresh_token(db, token_hash)
    if not stored_token or stored_token.revoked:
        logger.warning("Refresh rechazado: token inexistente o revocado")
        raise credentials_exception
    if stored_token.expires_at <= datetime.utcnow():
        logger.warning("Refresh rechazado: token expirado")
        raise credentials_exception

    user_id = token_payload.get("sub")
    if user_id is None or int(user_id) != stored_token.user_id:
        logger.warning("Refresh rechazado: user_id invalido")
        raise credentials_exception

    user = get_user_by_id(db, int(user_id))
    if user is None:
        logger.warning("Refresh rechazado: usuario no encontrado")
        raise credentials_exception

    revoke_refresh_token(db, stored_token)
    logger.info("Refresh exitoso para user_id=%s", user.id)
    return _issue_session_tokens(db, user)


@router.post("/logout")
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    token_hash = hash_token(payload.refresh_token)
    stored_token = get_refresh_token(db, token_hash)
    if stored_token and not stored_token.revoked:
        revoke_refresh_token(db, stored_token)
    logger.info("Logout ejecutado para refresh token")
    return {"ok": True}


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest):
    logger.info("Recuperacion de password no disponible. email=%s", payload.email)
    raise HTTPException(status_code=501, detail="Recuperacion de contrasena no disponible")


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest):
    logger.info("Reset de password no disponible")
    raise HTTPException(status_code=501, detail="Recuperacion de contrasena no disponible")


@router.get("/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    return current_user
