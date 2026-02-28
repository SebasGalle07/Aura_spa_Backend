from typing import Literal
from pydantic import EmailStr

from app.schemas.common import BaseSchema

Role = Literal["admin", "client", "professional"]


class UserBase(BaseSchema):
    email: EmailStr
    name: str
    phone: str | None = None
    role: Role
    created_at: str | None = None


class UserCreate(BaseSchema):
    email: EmailStr
    password: str
    name: str
    phone: str | None = None
    role: Role = "client"


class UserRegister(BaseSchema):
    email: EmailStr
    password: str
    name: str
    phone: str | None = None


class UserUpdate(BaseSchema):
    email: EmailStr | None = None
    name: str | None = None
    phone: str | None = None
    role: Role | None = None
    password: str | None = None


class UserOut(BaseSchema):
    id: int
    email: EmailStr
    name: str
    phone: str | None = None
    role: Role
    created_at: str | None = None


class PasswordChange(BaseSchema):
    current_password: str
    new_password: str
