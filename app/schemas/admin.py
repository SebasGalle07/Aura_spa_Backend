from app.schemas.common import BaseSchema
from app.schemas.appointment import AppointmentOut


class AdminSummary(BaseSchema):
    date: str
    today_total: int
    confirmed: int
    attended: int
    cancelled: int
    rescheduled: int
    agenda: list[AppointmentOut]
