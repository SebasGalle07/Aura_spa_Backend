from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.reservation_rules import APPOINTMENT_CONFIRMED, APPOINTMENT_RESCHEDULED
from app.core.time import utc_now
from app.crud.settlement import (
    create_settlement,
    create_settlement_payment,
    create_settlement_receipt,
    get_settlement_by_appointment,
    update_settlement,
)
from app.models.appointment import Appointment
from app.models.service import Service
from app.models.settlement import ServiceSettlement
from app.monitoring.metrics import observe_settlement_event, observe_settlement_payment

SETTLEMENT_PENDING = "pending_settlement"
SETTLEMENT_PARTIAL = "partially_paid"
SETTLEMENT_SETTLED = "settled"
SETTLEMENT_VOIDED = "voided"
SETTLEMENT_OPEN_STATUSES = {SETTLEMENT_PENDING, SETTLEMENT_PARTIAL}


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _compute_status(balance_amount: Decimal) -> str:
    return SETTLEMENT_SETTLED if balance_amount <= Decimal("0") else SETTLEMENT_PARTIAL


def ensure_settlement_for_appointment(db: Session, appointment: Appointment, service: Service) -> ServiceSettlement:
    existing = get_settlement_by_appointment(db, appointment.id)
    if existing:
        return existing
    if appointment.status not in {APPOINTMENT_CONFIRMED, APPOINTMENT_RESCHEDULED}:
        raise HTTPException(status_code=409, detail="Solo reservas confirmadas o reprogramadas pueden liquidarse")

    total_amount = _money(service.price)
    deposit_amount = _money(appointment.paid_amount or appointment.deposit_amount)
    balance_amount = max(total_amount - deposit_amount, Decimal("0"))
    status = SETTLEMENT_PENDING if balance_amount > Decimal("0") else SETTLEMENT_SETTLED
    settlement = create_settlement(
        db,
        {
            "appointment_id": appointment.id,
            "client_user_id": appointment.client_user_id,
            "service_id": appointment.service_id,
            "total_amount": total_amount,
            "deposit_amount": deposit_amount,
            "balance_amount": balance_amount,
            "paid_amount": deposit_amount,
            "status": status,
            "settled_at": utc_now() if status == SETTLEMENT_SETTLED else None,
        },
    )
    observe_settlement_event("created", settlement.status)
    return settlement


def register_settlement_payment(
    db: Session,
    settlement: ServiceSettlement,
    *,
    amount: Decimal,
    method: str,
    reference: str | None = None,
    notes: str | None = None,
    created_by_user_id: int | None = None,
):
    if settlement.status not in SETTLEMENT_OPEN_STATUSES:
        raise HTTPException(status_code=409, detail="La liquidacion no admite nuevos pagos")

    payment_amount = _money(amount)
    balance_amount = _money(settlement.balance_amount)
    if payment_amount > balance_amount:
        raise HTTPException(status_code=422, detail="El pago no puede ser mayor al saldo pendiente")

    payment = create_settlement_payment(
        db,
        {
            "settlement_id": settlement.id,
            "amount": payment_amount,
            "method": method,
            "reference": reference,
            "notes": notes,
            "created_by_user_id": created_by_user_id,
        },
    )

    new_paid_amount = _money(settlement.paid_amount) + payment_amount
    new_balance_amount = max(_money(settlement.total_amount) - new_paid_amount, Decimal("0"))
    new_status = _compute_status(new_balance_amount)
    update_settlement(
        db,
        settlement,
        {
            "paid_amount": new_paid_amount,
            "balance_amount": new_balance_amount,
            "status": new_status,
            "settled_at": utc_now() if new_status == SETTLEMENT_SETTLED else None,
        },
    )
    observe_settlement_payment(method)
    observe_settlement_event("payment_registered", settlement.status)
    return payment


def issue_receipt(db: Session, settlement: ServiceSettlement):
    if settlement.status != SETTLEMENT_SETTLED:
        raise HTTPException(status_code=409, detail="Solo se puede emitir comprobante para liquidaciones pagadas")
    if settlement.receipts:
        return settlement.receipts[-1]

    payload = {
        "settlement_id": settlement.id,
        "appointment_id": settlement.appointment_id,
        "service_id": settlement.service_id,
        "client_user_id": settlement.client_user_id,
        "total_amount": str(_money(settlement.total_amount)),
        "deposit_amount": str(_money(settlement.deposit_amount)),
        "paid_amount": str(_money(settlement.paid_amount)),
        "balance_amount": str(_money(settlement.balance_amount)),
        "status": settlement.status,
    }
    receipt = create_settlement_receipt(
        db,
        {
            "settlement_id": settlement.id,
            "receipt_number": f"TMP-{uuid4().hex[:16].upper()}",
            "total_amount": settlement.total_amount,
            "receipt_payload": payload,
        },
    )
    receipt.receipt_number = f"CSI-{utc_now().year}-{receipt.id:06d}"
    db.add(receipt)
    db.flush()
    observe_settlement_event("receipt_issued", settlement.status)
    return receipt
