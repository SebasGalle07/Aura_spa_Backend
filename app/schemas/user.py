import re
from datetime import datetime
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
    if len(clean) != 10:
        raise ValueError("El telefono debe tener exactamente 10 digitos.")
    return clean


def _validate_person_name(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    if not clean:
        raise ValueError("El nombre es obligatorio.")
    if re.search(r"\d", clean):
        raise ValueError("El nombre no puede contener numeros.")
    return clean


class UserBase(BaseSchema):
    email: EmailStr
    name: str
    phone: str | None = None
    role: Role
    email_verified: bool = True
    is_active: bool = True
    deactivated_at: datetime | None = None
    created_at: str | None = None


class UserCreate(BaseSchema):
    email: EmailStr
    password: str
    name: str
    phone: str | None = None
    role: Role = "client"

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        validated = _validate_person_name(value)
        assert validated is not None
        return validated

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        return _validate_digits_phone(value)


class UserRegister(BaseSchema):
    email: EmailStr
    password: str
    name: str
    phone: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        validated = _validate_person_name(value)
        assert validated is not None
        return validated

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str:
        validated = _validate_digits_phone(value)
        if validated is None:
            raise ValueError("El telefono es obligatorio.")
        return validated


class UserUpdate(BaseSchema):
    email: EmailStr | None = None
    name: str | None = None
    phone: str | None = None
    role: Role | None = None
    password: str | None = None
    email_verified: bool | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return _validate_person_name(value)

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
    email_verified: bool = True
    is_active: bool = True
    deactivated_at: datetime | None = None
    created_at: str | None = None


class PasswordChange(BaseSchema):
    current_password: str
    new_password: str
