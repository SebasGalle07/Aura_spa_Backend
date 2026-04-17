from datetime import timedelta
from hashlib import sha256
import re
from typing import Iterable
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now
from app.db.deps import get_db
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def validate_password_length(password: str) -> None:
    # bcrypt only supports 72 bytes
    if len(password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="Password too long (max 72 bytes)")


def validate_password_security(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="La contrasena debe tener al menos 8 caracteres")
    validate_password_length(password)
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="La contrasena debe incluir al menos una mayuscula")
    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="La contrasena debe incluir al menos una minuscula")
    if not re.search(r"\d", password):
        raise HTTPException(status_code=400, detail="La contrasena debe incluir al menos un numero")
    if not re.search(r"[^A-Za-z0-9]", password):
        raise HTTPException(status_code=400, detail="La contrasena debe incluir al menos un caracter especial")


def _hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> str:
    now = utc_now()
    expire = now + expires_delta
    to_encode = {
        "exp": expire,
        "iat": now,
        "sub": subject,
        "type": token_type,
        # Avoid issuing identical JWTs in the same second.
        "jti": uuid4().hex,
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_token(subject, "access", expires_delta)


def create_refresh_token(subject: str, expires_delta: timedelta | None = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return _create_token(subject, "refresh", expires_delta)


def create_reset_token(subject: str, expires_delta: timedelta | None = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)
    return _create_token(subject, "reset", expires_delta)


def create_email_verification_token(subject: str, expires_delta: timedelta | None = None) -> str:
    if expires_delta is None:
        expires_delta = timedelta(hours=settings.VERIFY_EMAIL_TOKEN_EXPIRE_HOURS)
    return _create_token(subject, "verify_email", expires_delta)


def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        token_type = payload.get("type")
        if token_type and token_type != "access":
            raise credentials_exception
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    try:
        parsed_user_id = int(user_id)
    except (TypeError, ValueError):
        raise credentials_exception
    user = db.get(User, parsed_user_id)
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="La cuenta se encuentra desactivada")
    return user


def get_optional_user(db: Session = Depends(get_db), token: str | None = Depends(optional_oauth2_scheme)):
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        token_type = payload.get("type")
        user_id = payload.get("sub")
        if token_type and token_type != "access":
            return None
        if user_id is None:
            return None
    except JWTError:
        return None
    try:
        parsed_user_id = int(user_id)
    except (TypeError, ValueError):
        return None
    user = db.get(User, parsed_user_id)
    if user is None or not user.is_active:
        return None
    return user


def decode_token(token: str):
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def hash_token(token: str) -> str:
    return _hash_token(token)


def require_roles(*roles: Iterable[str]):
    def _role_checker(current_user=Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return current_user

    return _role_checker
