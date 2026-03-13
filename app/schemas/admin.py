from app.schemas.common import BaseSchema
from app.schemas.appointment import AppointmentOut


class AdminSummary(BaseSchema):
    date: str
    today_total: int
    pending_payment: int
    confirmed: int
    completed: int
    expired: int
    cancelled: int
    rescheduled: int
    agenda: list[AppointmentOut]


class UploadImageResponse(BaseSchema):
    url: str
