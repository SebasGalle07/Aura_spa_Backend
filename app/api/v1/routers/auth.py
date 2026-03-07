from datetime import datetime
import logging
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.mailer import send_password_reset_email
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_reset_token,
    decode_token,
    get_current_user,
    get_password_hash,
    hash_token,
    validate_password_length,
)
from app.crud.token import (
    get_refresh_token,
    get_reset_token,
    mark_reset_used,
    revoke_refresh_token,
    store_refresh_token,
    store_reset_token,
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
    exp = payload.get('exp')
    if exp is None:
        raise HTTPException(status_code=500, detail='Token without expiry')
    return datetime.utcfromtimestamp(exp)


def _issue_session_tokens(db: Session, user) -> dict:
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))
    refresh_expiry = _expiry_datetime_from_token(refresh_token)
    store_refresh_token(db, user.id, hash_token(refresh_token), refresh_expiry)
    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'bearer',
        'user': user,
    }


def _build_reset_link(token: str) -> str:
    base = settings.FRONTEND_APP_URL.rstrip('/')
    return f'{base}/forgot-password?token={quote(token)}'


@router.post('/register', response_model=Token)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    validate_password_length(user_in.password)
    if get_user_by_email(db, user_in.email):
        logger.warning('Registro rechazado por email duplicado: %s', user_in.email)
        raise HTTPException(status_code=400, detail='Email already registered')
    user = create_user(db, user_in, role='client')
    logger.info('Usuario registrado: id=%s email=%s', user.id, user.email)
    return _issue_session_tokens(db, user)


@router.post('/login', response_model=Token)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    validate_password_length(data.password)
    user = authenticate_user(db, data.email, data.password)
    if not user:
        logger.warning('Login fallido para email=%s', data.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Incorrect email or password')
    logger.info('Login exitoso: id=%s email=%s', user.id, user.email)
    return _issue_session_tokens(db, user)


@router.post('/refresh', response_model=Token)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Invalid refresh token',
    )
    try:
        token_payload = decode_token(payload.refresh_token)
    except JWTError:
        raise credentials_exception

    if token_payload.get('type') != 'refresh':
        raise credentials_exception

    token_hash = hash_token(payload.refresh_token)
    stored_token = get_refresh_token(db, token_hash)
    if not stored_token or stored_token.revoked:
        logger.warning('Refresh rechazado: token inexistente o revocado')
        raise credentials_exception
    if stored_token.expires_at <= datetime.utcnow():
        logger.warning('Refresh rechazado: token expirado')
        raise credentials_exception

    user_id = token_payload.get('sub')
    if user_id is None or int(user_id) != stored_token.user_id:
        logger.warning('Refresh rechazado: user_id invalido')
        raise credentials_exception

    user = get_user_by_id(db, int(user_id))
    if user is None:
        logger.warning('Refresh rechazado: usuario no encontrado')
        raise credentials_exception

    revoke_refresh_token(db, stored_token)
    logger.info('Refresh exitoso para user_id=%s', user.id)
    return _issue_session_tokens(db, user)


@router.post('/logout')
def logout(payload: RefreshRequest, db: Session = Depends(get_db)):
    token_hash = hash_token(payload.refresh_token)
    stored_token = get_refresh_token(db, token_hash)
    if stored_token and not stored_token.revoked:
        revoke_refresh_token(db, stored_token)
    logger.info('Logout ejecutado para refresh token')
    return {'ok': True}


@router.post('/forgot-password', response_model=ForgotPasswordResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = get_user_by_email(db, payload.email)
    reset_token: str | None = None

    if user:
        token = create_reset_token(subject=str(user.id))
        expires_at = _expiry_datetime_from_token(token)
        store_reset_token(db, user.id, hash_token(token), expires_at)

        if settings.smtp_enabled:
            try:
                send_password_reset_email(user.email, _build_reset_link(token))
                logger.info('Correo de recuperacion enviado a %s', user.email)
            except Exception as exc:
                logger.exception('Fallo envio de correo de recuperacion para %s: %s', user.email, exc)
        elif settings.RETURN_RESET_TOKEN:
            reset_token = token
        else:
            logger.warning('SMTP no configurado: no se pudo enviar recuperacion para %s', user.email)

    return {'ok': True, 'reset_token': reset_token}


@router.post('/reset-password')
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    validate_password_length(payload.new_password)

    invalid_token_error = HTTPException(status_code=400, detail='Invalid or expired token')
    try:
        token_payload = decode_token(payload.token)
    except JWTError:
        raise invalid_token_error

    if token_payload.get('type') != 'reset':
        raise invalid_token_error

    token_hash = hash_token(payload.token)
    token_row = get_reset_token(db, token_hash)
    if not token_row or token_row.used or token_row.expires_at <= datetime.utcnow():
        raise invalid_token_error

    user_id = token_payload.get('sub')
    if user_id is None or int(user_id) != token_row.user_id:
        raise invalid_token_error

    user = get_user_by_id(db, token_row.user_id)
    if not user:
        raise invalid_token_error

    user.hashed_password = get_password_hash(payload.new_password)
    token_row.used = True
    db.add(user)
    db.add(token_row)
    db.commit()

    logger.info('Contrasena restablecida para user_id=%s', user.id)
    return {'ok': True}


@router.get('/me', response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    return current_user
