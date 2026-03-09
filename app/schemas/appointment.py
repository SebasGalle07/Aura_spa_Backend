from typing import Literal
from pydantic import EmailStr, Field, field_validator

from app.schemas.common import BaseSchema

Status = Literal["confirmed", "cancelled", "attended", "rescheduled"]


def _validate_digits_phone(value: str | None) -> str | None:
    if value is None:
        return None
    clean = value.strip()
    if not clean:
        return None
    if not clean.isdigit():
        raise ValueError("El telefono solo permite numeros.")
    return clean


class AppointmentHistoryItem(BaseSchema):
    action: str
    at: str


class AppointmentCreate(BaseSchema):
    service_id: int
    professional_id: int
    date: str
    time: str
    client_name: str | None = None
    client_email: EmailStr | None = None
    client_phone: str | None = None
    notes: str | None = ""

    @field_validator("client_phone")
    @classmethod
    def validate_client_phone(cls, value: str | None) -> str | None:
        return _validate_digits_phone(value)


class AppointmentOut(BaseSchema):
    id: int
    client_name: str
    client_email: EmailStr
    client_phone: str | None = None
    service_id: int
    professional_id: int
    date: str
    time: str
    status: Status
    notes: str | None = ""
    history: list[AppointmentHistoryItem] = Field(default_factory=list)


class AppointmentReschedule(BaseSchema):
    date: str
    time: str


class AppointmentStatusUpdate(BaseSchema):
    status: Status
    notes: str | None = None


class AppointmentNotes(BaseSchema):
    notes: str | None = None
