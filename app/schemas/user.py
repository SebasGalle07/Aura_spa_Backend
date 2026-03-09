from typing import Literal
from pydantic import EmailStr, field_validator

from app.schemas.common import BaseSchema

Role = Literal["admin", "client", "professional"]


def _validate_digits_phone(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    if not clean:
        return None
    if not clean.isdigit():
        raise ValueError("El telefono solo permite numeros.")
    return clean


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

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return _validate_digits_phone(value)


class UserRegister(BaseSchema):
    email: EmailStr
    password: str
    name: str
    phone: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return _validate_digits_phone(value)


class UserUpdate(BaseSchema):
    email: EmailStr | None = None
    name: str | None = None
    phone: str | None = None
    role: Role | None = None
    password: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return _validate_digits_phone(value)


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
