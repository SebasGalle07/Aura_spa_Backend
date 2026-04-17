from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.time import utc_now
from app.db.base import Base


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    client_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_email: Mapped[str] = mapped_column(String(255), nullable=False)
    client_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id"), nullable=False)
    professional_id: Mapped[int] = mapped_column(Integer, ForeignKey("professionals.id"), nullable=False)

    date: Mapped[str] = mapped_column(String(10), nullable=False)
    time: Mapped[str] = mapped_column(String(5), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    payment_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    deposit_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    balance_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    paid_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payment_transaction_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payment_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, default=utc_now, onupdate=utc_now
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=False, default="")
    history: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    status_logs: Mapped[list["AppointmentStatusLog"]] = relationship(
        "AppointmentStatusLog",
        back_populates="appointment",
        cascade="all, delete-orphan",
    )
    reschedules: Mapped[list["AppointmentReschedule"]] = relationship(
        "AppointmentReschedule",
        back_populates="appointment",
        cascade="all, delete-orphan",
    )
    payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="appointment",
        cascade="all, delete-orphan",
    )


class AppointmentStatusLog(Base):
    __tablename__ = "appointment_status_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    appointment_id: Mapped[int] = mapped_column(Integer, ForeignKey("appointments.id"), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False, default="system")
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)

    appointment: Mapped["Appointment"] = relationship("Appointment", back_populates="status_logs")


class AppointmentReschedule(Base):
    __tablename__ = "appointment_reschedules"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    appointment_id: Mapped[int] = mapped_column(Integer, ForeignKey("appointments.id"), nullable=False, index=True)
    old_date: Mapped[str] = mapped_column(String(10), nullable=False)
    old_time: Mapped[str] = mapped_column(String(5), nullable=False)
    new_date: Mapped[str] = mapped_column(String(10), nullable=False)
    new_time: Mapped[str] = mapped_column(String(5), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False, default="system")
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)

    appointment: Mapped["Appointment"] = relationship("Appointment", back_populates="reschedules")


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    appointment_id: Mapped[int] = mapped_column(Integer, ForeignKey("appointments.id"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="mock")
    method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="COP")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    provider_reference: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    provider_tx_id: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, default=utc_now, onupdate=utc_now
    )

    appointment: Mapped["Appointment"] = relationship("Appointment", back_populates="payments")
