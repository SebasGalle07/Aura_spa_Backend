from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.token import RefreshToken, PasswordResetToken


def store_refresh_token(db: Session, user_id: int, token_hash: str, expires_at: datetime):
    obj = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at, revoked=False)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_refresh_token(db: Session, token_hash: str):
    return db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))


def revoke_refresh_token(db: Session, token_obj: RefreshToken):
    token_obj.revoked = True
    db.add(token_obj)
    db.commit()
    db.refresh(token_obj)
    return token_obj


def store_reset_token(db: Session, user_id: int, token_hash: str, expires_at: datetime):
    obj = PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at, used=False)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def get_reset_token(db: Session, token_hash: str):
    return db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash))


def mark_reset_used(db: Session, token_obj: PasswordResetToken):
    token_obj.used = True
    db.add(token_obj)
    db.commit()
    db.refresh(token_obj)
    return token_obj
