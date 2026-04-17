from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.time import utc_now
from app.db.base import Base


class ServiceSettlement(Base):
    __tablename__ = "service_settlements"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    appointment_id: Mapped[int] = mapped_column(Integer, ForeignKey("appointments.id"), nullable=False, unique=True, index=True)
    client_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id"), nullable=False, index=True)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    deposit_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    balance_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    paid_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_settlement", index=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    payments: Mapped[list["SettlementPayment"]] = relationship(
        "SettlementPayment",
        back_populates="settlement",
        cascade="all, delete-orphan",
        order_by="SettlementPayment.id",
    )
    receipts: Mapped[list["SettlementReceipt"]] = relationship(
        "SettlementReceipt",
        back_populates="settlement",
        cascade="all, delete-orphan",
        order_by="SettlementReceipt.id",
    )


class SettlementPayment(Base):
    __tablename__ = "settlement_payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    settlement_id: Mapped[int] = mapped_column(Integer, ForeignKey("service_settlements.id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, index=True)

    settlement: Mapped["ServiceSettlement"] = relationship("ServiceSettlement", back_populates="payments")


class SettlementReceipt(Base):
    __tablename__ = "settlement_receipts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    settlement_id: Mapped[int] = mapped_column(Integer, ForeignKey("service_settlements.id"), nullable=False, index=True)
    receipt_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True, index=True)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, index=True)
    receipt_payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    settlement: Mapped["ServiceSettlement"] = relationship("ServiceSettlement", back_populates="receipts")
