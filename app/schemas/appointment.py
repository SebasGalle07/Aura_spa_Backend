from typing import Literal
from pydantic import EmailStr

from app.schemas.common import BaseSchema

Status = Literal["pending", "confirmed", "cancelled", "attended", "rescheduled"]


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
    history: list[AppointmentHistoryItem] = []


class AppointmentReschedule(BaseSchema):
    date: str
    time: str


class AppointmentStatusUpdate(BaseSchema):
    status: Status
    notes: str | None = None


class AppointmentNotes(BaseSchema):
    notes: str | None = None
