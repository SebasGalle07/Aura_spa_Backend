from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema


SettlementStatus = Literal["pending_settlement", "partially_paid", "settled", "voided"]


class SettlementPaymentCreate(BaseSchema):
    amount: Decimal = Field(gt=0)
    method: str
    reference: str | None = None
    notes: str | None = None

    @field_validator("method")
    @classmethod
    def validate_method(cls, value: str) -> str:
        clean = value.strip()
        if not clean:
            raise ValueError("El metodo de pago es obligatorio")
        return clean


class SettlementPaymentOut(BaseSchema):
    id: int
    settlement_id: int
    amount: Decimal
    method: str
    reference: str | None = None
    notes: str | None = None
    created_by_user_id: int | None = None
    created_at: datetime


class SettlementReceiptOut(BaseSchema):
    id: int
    settlement_id: int
    receipt_number: str
    total_amount: Decimal
    issued_at: datetime
    receipt_payload: dict


class ServiceSettlementOut(BaseSchema):
    id: int
    appointment_id: int
    client_user_id: int | None = None
    service_id: int
    total_amount: Decimal
    deposit_amount: Decimal
    balance_amount: Decimal
    paid_amount: Decimal
    status: SettlementStatus
    settled_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ServiceSettlementDetail(ServiceSettlementOut):
    payments: list[SettlementPaymentOut] = Field(default_factory=list)
    receipts: list[SettlementReceiptOut] = Field(default_factory=list)
