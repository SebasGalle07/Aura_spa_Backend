from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.mailer import send_email_change_alert_email
from app.core.security import require_roles, get_current_user, verify_password, get_password_hash, validate_password_security
from app.db.deps import get_db
from app.crud.user import get_user_by_id, get_user_by_email, create_user, update_user
from app.models.user import User
from app.schemas.user import UserOut, UserCreate, UserUpdate, PasswordChange
from app.services.email_verification import ensure_verification_email_available, send_verification_email_or_raise

router = APIRouter()


@router.get("/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserOut)
def update_me(payload: UserUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    data = payload.model_dump(exclude_unset=True, by_alias=False)
    previous_email = current_user.email
    for key in list(data.keys()):
        if key not in {"name", "email", "phone"}:
            data.pop(key, None)
    if "email" in data:
        existing = get_user_by_email(db, data["email"])
        if existing and existing.id != current_user.id:
            raise HTTPException(status_code=400, detail="Email already registered")
        if data["email"] != current_user.email:
            data["email_verified"] = False
            ensure_verification_email_available()
            send_email_change_alert_email(
                previous_email,
                current_user.name,
                previous_email,
                data["email"],
                requested_at=datetime.utcnow(),
            )
    updated = update_user(db, current_user, UserUpdate(**data))
    if "email_verified" in data:
        send_verification_email_or_raise(db, updated)
    return updated


@router.post("/me/password", response_model=UserOut)
def change_password(payload: PasswordChange, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    validate_password_security(payload.new_password)
    current_user.hashed_password = get_password_hash(payload.new_password)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("", response_model=list[UserOut], dependencies=[Depends(require_roles("admin"))])
def list_users(db: Session = Depends(get_db)):
    return list(db.scalars(select(User)).all())


@router.post("", response_model=UserOut, dependencies=[Depends(require_roles("admin"))])
def create_user_admin(payload: UserCreate, db: Session = Depends(get_db)):
    if get_user_by_email(db, payload.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    validate_password_security(payload.password)
    return create_user(db, payload, role=payload.role)


@router.put("/{user_id}", response_model=UserOut, dependencies=[Depends(require_roles("admin"))])
def update_user_admin(user_id: int, payload: UserUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    original_email = user.email
    if user.id == current_user.id and payload.role and payload.role != current_user.role:
        raise HTTPException(status_code=400, detail="Cannot change your own role")
    if payload.email:
        existing = get_user_by_email(db, payload.email)
        if existing and existing.id != user.id:
            raise HTTPException(status_code=400, detail="Email already registered")
        if payload.email != original_email:
            ensure_verification_email_available()
            send_email_change_alert_email(
                original_email,
                user.name,
                original_email,
                payload.email,
                requested_at=datetime.utcnow(),
            )
            payload = UserUpdate(**(payload.model_dump(exclude_unset=True, by_alias=False) | {"email_verified": False}))
    if payload.password:
        validate_password_security(payload.password)
    updated = update_user(db, user, payload)
    if payload.email and payload.email != original_email:
        send_verification_email_or_raise(db, updated)
    return updated


@router.delete("/{user_id}", dependencies=[Depends(require_roles("admin"))])
def delete_user_admin(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    user = get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    if user.role == "admin":
        admins = list(db.scalars(select(User).where(User.role == "admin")).all())
        if len(admins) <= 1:
            raise HTTPException(status_code=400, detail="At least one admin must exist")
    db.delete(user)
    db.commit()
    return {"ok": True}
