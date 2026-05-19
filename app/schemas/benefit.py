from datetime import datetime
from decimal import Decimal
from typing import Literal

from app.schemas.common import BaseSchema


BenefitStatus = Literal["active", "reserved", "used", "expired"]


class ClientBenefitOut(BaseSchema):
    id: int
    client_user_id: int
    source_service_case_id: int
    discount_percent: Decimal
    status: BenefitStatus
    reserved_appointment_id: int | None = None
    used_appointment_id: int | None = None
    granted_at: datetime
    expires_at: datetime
    used_at: datetime | None = None
