from datetime import datetime
import logging
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token as google_id_token
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.mailer import send_email_verification_email, send_password_reset_email
from app.core.security import (
    create_access_token,
    create_email_verification_token,
    create_refresh_token,
    create_reset_token,
    decode_token,
    get_current_user,
    get_password_hash,
    hash_token,
    validate_password_security,
)
from app.crud.token import (
    get_email_verification_token,
    get_recent_email_verification_token,
    get_refresh_token,
    get_reset_token,
    revoke_refresh_token,
    store_email_verification_token,
    store_refresh_token,
    store_reset_token,
)
from app.crud.user import authenticate_user, create_user, get_user_by_email, get_user_by_id
from app.db.deps import get_db
from app.schemas.auth import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    GoogleLoginRequest,
    LoginRequest,
    RefreshRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    Token,
    VerifyEmailRequest,
    VerifyEmailResponse,
)
from app.schemas.user import UserOut, UserRegister

router = APIRouter()
logger = logging.getLogger(__name__)


def _expiry_datetime_from_token(token: str) -> datetime:
    payload = decode_token(token)
    exp = payload.get('exp')
    if exp is None:
        raise HTTPException(status_code=500, detail='Token sin expiracion')
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


def _build_verify_email_link(token: str) -> str:
    base = settings.FRONTEND_APP_URL.rstrip('/')
    return f'{base}/verify-email?token={quote(token)}'


def _send_verification_email_or_raise(db: Session, user) -> None:
    if not settings.smtp_enabled:
        logger.error('Verificacion por correo no disponible: SMTP no configurado')
        raise HTTPException(status_code=503, detail='Verificacion por correo no disponible')

    token = create_email_verification_token(subject=str(user.id))
    expires_at = _expiry_datetime_from_token(token)

    try:
        send_email_verification_email(user.email, _build_verify_email_link(token))
        store_email_verification_token(db, user.id, hash_token(token), expires_at)
        logger.info('Correo de verificacion enviado a %s', user.email)
    except Exception as exc:
        logger.exception('Fallo envio de verificacion para %s: %s', user.email, exc)
        raise HTTPException(status_code=500, detail='No fue posible enviar el correo de verificacion')


def _verify_google_id_token(id_token: str) -> dict:
    if not settings.google_login_enabled:
        logger.warning('Login con Google no disponible: GOOGLE_CLIENT_IDS vacio')
        raise HTTPException(status_code=503, detail='Login con Google no disponible')

    try:
        token_data = google_id_token.verify_oauth2_token(id_token, GoogleRequest())
    except ValueError:
        logger.warning('Google login rechazado: token invalido')
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token de Google invalido')

    issuer = token_data.get('iss')
    if issuer not in ('accounts.google.com', 'https://accounts.google.com'):
        logger.warning('Google login rechazado: issuer invalido=%s', issuer)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token de Google invalido')

    audience = token_data.get('aud')
    if audience not in settings.GOOGLE_CLIENT_IDS:
        logger.warning('Google login rechazado: audience invalido=%s', audience)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token de Google invalido')

    if token_data.get('email_verified') is not True:
        logger.warning('Google login rechazado: email sin verificar')
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='El correo de Google no esta verificado')

    return token_data


@router.post('/register', response_model=RegisterResponse)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    validate_password_security(user_in.password)
    if not settings.smtp_enabled:
        raise HTTPException(status_code=503, detail='Registro temporalmente no disponible')

    existing_user = get_user_by_email(db, user_in.email)
    if existing_user:
        if not existing_user.email_verified:
            _send_verification_email_or_raise(db, existing_user)
            return {'ok': True, 'email_verification_required': True}
        logger.warning('Registro rechazado por email duplicado: %s', user_in.email)
        raise HTTPException(status_code=400, detail='El correo ya esta registrado')

    user = create_user(db, user_in, role='client', email_verified=False)
    logger.info('Usuario registrado pendiente de verificacion: id=%s email=%s', user.id, user.email)
    try:
        _send_verification_email_or_raise(db, user)
    except HTTPException:
        db.delete(user)
        db.commit()
        raise
    return {'ok': True, 'email_verification_required': True}


@router.post('/resend-verification', response_model=VerifyEmailResponse)
def resend_verification(payload: ResendVerificationRequest, db: Session = Depends(get_db)):
    user = get_user_by_email(db, payload.email)
    if not user:
        return {'ok': True}

    if user.email_verified:
        return {'ok': True}

    recent_token = get_recent_email_verification_token(db, user.id)
    if recent_token:
        elapsed = (datetime.utcnow() - recent_token.created_at).total_seconds()
        if elapsed < settings.VERIFY_EMAIL_RESEND_SECONDS:
            return {'ok': True}

    _send_verification_email_or_raise(db, user)
    return {'ok': True}


@router.post('/verify-email', response_model=VerifyEmailResponse)
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)):
    invalid_token_error = HTTPException(status_code=400, detail='Token de verificacion invalido o expirado')
    try:
        token_payload = decode_token(payload.token)
    except JWTError:
        raise invalid_token_error

    if token_payload.get('type') != 'verify_email':
        raise invalid_token_error

    token_hash = hash_token(payload.token)
    token_row = get_email_verification_token(db, token_hash)
    if not token_row or token_row.used or token_row.expires_at <= datetime.utcnow():
        raise invalid_token_error

    user_id = token_payload.get('sub')
    if user_id is None or int(user_id) != token_row.user_id:
        raise invalid_token_error

    user = get_user_by_id(db, token_row.user_id)
    if not user:
        raise invalid_token_error

    user.email_verified = True
    token_row.used = True
    db.add(user)
    db.add(token_row)
    db.commit()

    logger.info('Correo verificado para user_id=%s', user.id)
    return {'ok': True}


@router.post('/login', response_model=Token)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, data.email, data.password)
    if not user:
        logger.warning('Login fallido para email=%s', data.email)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Correo o contrasena incorrectos')

    if not user.email_verified:
        logger.warning('Login bloqueado por correo no verificado: user_id=%s email=%s', user.id, user.email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Debes verificar tu correo antes de iniciar sesion',
        )

    logger.info('Login exitoso: id=%s email=%s', user.id, user.email)
    return _issue_session_tokens(db, user)


@router.post('/google', response_model=Token)
def login_google(payload: GoogleLoginRequest, db: Session = Depends(get_db)):
    token_data = _verify_google_id_token(payload.id_token)
    email = (token_data.get('email') or '').strip().lower()
    if not email:
        logger.warning('Google login rechazado: token sin email')
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token de Google invalido')

    user = get_user_by_email(db, email)
    if not user:
        default_name = email.split('@', 1)[0]
        raw_name = (token_data.get('name') or token_data.get('given_name') or default_name).strip() or default_name
        name = ''.join(ch for ch in raw_name if not ch.isdigit()).strip() or 'Usuario Google'
        google_user = UserRegister(
            email=email,
            password=secrets.token_urlsafe(32),
            name=name,
            phone=None,
        )
        user = create_user(db, google_user, role='client', email_verified=True)
        logger.info('Usuario creado por login Google: id=%s email=%s', user.id, user.email)
    elif not user.email_verified:
        user.email_verified = True
        db.add(user)
        db.commit()
        db.refresh(user)

    logger.info('Login Google exitoso: id=%s email=%s', user.id, user.email)
    return _issue_session_tokens(db, user)


@router.post('/refresh', response_model=Token)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Refresh token invalido',
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
    if not settings.smtp_enabled and not settings.RETURN_RESET_TOKEN:
        logger.error('Recuperacion no disponible: SMTP no configurado y RETURN_RESET_TOKEN=False')
        raise HTTPException(status_code=503, detail='Recuperacion por correo no disponible')

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
    validate_password_security(payload.new_password)

    invalid_token_error = HTTPException(status_code=400, detail='Token invalido o expirado')
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
