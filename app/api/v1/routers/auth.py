from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_current_user, validate_password_length
from app.db.deps import get_db
from app.crud.user import authenticate_user, create_user, get_user_by_email
from app.schemas.auth import LoginRequest, Token
from app.schemas.user import UserRegister, UserOut

router = APIRouter()


@router.post("/register", response_model=Token)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    validate_password_length(user_in.password)
    if get_user_by_email(db, user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = create_user(db, user_in, role="client")
    token = create_access_token(subject=str(user.id))
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/login", response_model=Token)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    validate_password_length(data.password)
    user = authenticate_user(db, data.email, data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    token = create_access_token(subject=str(user.id))
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.get("/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    return current_user
