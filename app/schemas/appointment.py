from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import EmailStr, Field, field_validator

from app.schemas.common import BaseSchema

AppointmentStatus = Literal[
    "pending_payment",
    "confirmed",
    "expired",
    "cancelled",
    "rescheduled",
    "completed",
    "no_show",
]
PaymentStatus = Literal["pending", "approved", "rejected", "expired", "cancelled", "voided"]


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

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        datetime.strptime(value, "%Y-%m-%d")
        return value

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: str) -> str:
        datetime.strptime(value, "%H:%M")
        return value


class AppointmentOut(BaseSchema):
    id: int
    client_user_id: int | None = None
    client_name: str
    client_email: EmailStr
    client_phone: str | None = None
    service_id: int
    professional_id: int
    date: str
    time: str
    status: AppointmentStatus
    payment_status: PaymentStatus = "pending"
    payment_due_at: datetime | None = None
    deposit_amount: Decimal = Decimal("0")
    balance_amount: Decimal = Decimal("0")
    paid_amount: Decimal = Decimal("0")
    paid_at: datetime | None = None
    payment_method: str | None = None
    payment_reference: str | None = None
    payment_transaction_id: str | None = None
    payment_provider: str | None = None
    cancelled_at: datetime | None = None
    notes: str | None = ""
    history: list[AppointmentHistoryItem] = Field(default_factory=list)

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value: str) -> str:
        return "completed" if value == "attended" else value


class AppointmentReschedule(BaseSchema):
    date: str
    time: str
    reason: str | None = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str) -> str:
        datetime.strptime(value, "%Y-%m-%d")
        return value

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: str) -> str:
        datetime.strptime(value, "%H:%M")
        return value


class AppointmentNotes(BaseSchema):
    notes: str | None = None


class AppointmentPaymentInit(BaseSchema):
    method: str | None = None


class AppointmentPaymentCheckoutData(BaseSchema):
    provider: str
    public_key: str | None = None
    checkout_url: str | None = None
    merchant_id: str | None = None
    account_id: str | None = None
    reference_code: str | None = None
    description: str | None = None
    amount: str | None = None
    tax: str | None = None
    tax_return_base: str | None = None
    signature: str | None = None
    signature_algorithm: str | None = None
    test: str | None = None
    buyer_email: EmailStr | None = None
    response_url: str | None = None
    confirmation_url: str | None = None
    payer_full_name: str | None = None
    mobile_phone: str | None = None
    amount_in_cents: int | None = None
    currency: str | None = None
    reference: str | None = None
    integrity_signature: str | None = None
    redirect_url: str | None = None
    expiration_time: str | None = None
    customer_email: EmailStr | None = None
    customer_full_name: str | None = None
    customer_phone_number: str | None = None


class AppointmentPaymentInitResponse(BaseSchema):
    appointment_id: int
    payment_reference: str
    provider: str
    amount: Decimal
    currency: str = "COP"
    payment_due_at: datetime | None = None
    status: PaymentStatus
    checkout_url: str | None = None
    checkout_data: AppointmentPaymentCheckoutData | None = None


class AppointmentPaymentOut(BaseSchema):
    id: int
    appointment_id: int
    provider: str
    method: str | None = None
    amount: Decimal
    currency: str
    status: PaymentStatus
    provider_reference: str
    provider_tx_id: str | None = None
    paid_at: datetime | None = None
    metadata_json: dict | None = None
    created_at: datetime
    updated_at: datetime


class PaymentWebhookPayload(BaseSchema):
    provider_reference: str
    provider_tx_id: str
    status: Literal["approved", "rejected", "expired", "cancelled"]
    method: str | None = None
    amount: Decimal | None = None
    metadata: dict | None = None


class MockPaymentResultPayload(BaseSchema):
    provider_reference: str
    status: Literal["approved", "rejected", "expired", "cancelled"]
    method: str | None = None


class PaymentWebhookResponse(BaseSchema):
    ok: bool = True
    appointment_id: int
    appointment_status: AppointmentStatus
    payment_status: PaymentStatus


class PaymentSyncResponse(PaymentWebhookResponse):
    provider_reference: str
    provider_transaction_id: str | None = None
    provider_transaction_status: str | None = None
