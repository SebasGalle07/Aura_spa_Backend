from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


class ClientBenefit(Base):
    __tablename__ = "client_benefits"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    client_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    source_service_case_id: Mapped[int] = mapped_column(ForeignKey("service_cases.id"), nullable=False, unique=True, index=True)
    discount_percent: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    reserved_appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"), nullable=True, unique=True)
    used_appointment_id: Mapped[int | None] = mapped_column(ForeignKey("appointments.id"), nullable=True, unique=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
