from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserRegister, UserUpdate


def get_user_by_id(db: Session, user_id: int):
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str):
    return db.scalar(select(User).where(User.email == email))


def create_user(
    db: Session,
    user_in: UserCreate | UserRegister,
    role: str | None = None,
    email_verified: bool = True,
):
    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        role=role or getattr(user_in, "role", "client"),
        name=user_in.name,
        phone=getattr(user_in, "phone", None),
        email_verified=email_verified,
        created_at=date.today().isoformat(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, db_user: User, user_in: UserUpdate):
    data = user_in.model_dump(exclude_unset=True, by_alias=False)
    if "password" in data:
        db_user.hashed_password = get_password_hash(data.pop("password"))
    for field, value in data.items():
        setattr(db_user, field, value)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
