import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.mailer import send_settlement_receipt_email
from app.core.security import get_current_user, require_roles
from app.crud.appointment import get_appointment
from app.crud.audit import create_audit_log
from app.crud.professional import get_professional
from app.crud.service import get_service
from app.crud.settlement import get_settlement, list_settlements, list_settlements_by_client
from app.db.deps import get_db
from app.schemas.settlement import (
    ServiceSettlementDetail,
    ServiceSettlementOut,
    SettlementPaymentCreate,
    SettlementReceiptOut,
)
from app.services.settlement_workflow import issue_receipt, register_settlement_payment

router = APIRouter()
logger = logging.getLogger(__name__)


def _enforce_settlement_owner_or_admin(db: Session, settlement, current_user):
    if current_user.role == "admin":
        return
    appointment = get_appointment(db, settlement.appointment_id)
    if settlement.client_user_id == current_user.id:
        return
    if appointment and appointment.client_email == current_user.email:
        return
    raise HTTPException(status_code=403, detail="Not enough permissions")


def _money_label(value) -> str:
    try:
        return f"${int(value):,}".replace(",", ".")
    except Exception:
        return f"${value}"


def _send_receipt_email_if_possible(db: Session, settlement, receipt) -> None:
    appointment = get_appointment(db, settlement.appointment_id)
    service = get_service(db, settlement.service_id)
    professional = get_professional(db, appointment.professional_id) if appointment else None

    if not (settings.smtp_enabled and appointment and service and appointment.client_email):
        return

    try:
        send_settlement_receipt_email(
            to_email=appointment.client_email,
            client_name=appointment.client_name,
            receipt_number=receipt.receipt_number,
            service_name=service.name,
            professional_name=professional.name if professional else "Profesional asignado",
            appointment_date=appointment.date,
            appointment_time=appointment.time,
            total_amount=_money_label(settlement.total_amount),
            deposit_amount=_money_label(settlement.deposit_amount),
            paid_amount=_money_label(settlement.paid_amount),
            balance_amount=_money_label(settlement.balance_amount),
            issued_at=receipt.issued_at,
        )
    except Exception:
        logger.exception("No fue posible enviar comprobante %s por correo", receipt.receipt_number)


@router.get("", response_model=list[ServiceSettlementOut], dependencies=[Depends(require_roles("admin"))])
def list_all(
    status: str | None = None,
    appointment_id: int | None = None,
    service_id: int | None = None,
    client_user_id: int | None = None,
    db: Session = Depends(get_db),
):
    return list_settlements(
        db,
        status=status,
        appointment_id=appointment_id,
        service_id=service_id,
        client_user_id=client_user_id,
    )


@router.get("/my", response_model=list[ServiceSettlementOut], dependencies=[Depends(require_roles("client"))])
def list_my(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return list_settlements_by_client(db, current_user.id, current_user.email)


@router.get("/{settlement_id}", response_model=ServiceSettlementDetail)
def get_one(settlement_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    settlement = get_settlement(db, settlement_id)
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")
    _enforce_settlement_owner_or_admin(db, settlement, current_user)
    return settlement


@router.post(
    "/{settlement_id}/payments",
    response_model=ServiceSettlementDetail,
    dependencies=[Depends(require_roles("admin"))],
)
def register_payment(
    settlement_id: int,
    payload: SettlementPaymentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    settlement = get_settlement(db, settlement_id, for_update=True)
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")

    payment = register_settlement_payment(
        db,
        settlement,
        amount=payload.amount,
        method=payload.method,
        reference=payload.reference,
        notes=payload.notes,
        created_by_user_id=current_user.id,
    )
    create_audit_log(
        db,
        action="settlement_payment_registered",
        entity_type="service_settlement",
        entity_id=settlement.id,
        actor=current_user,
        new_value={
            "payment_id": payment.id,
            "amount": str(payment.amount),
            "method": payment.method,
            "status": settlement.status,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    return get_settlement(db, settlement_id)


@router.post(
    "/{settlement_id}/issue-receipt",
    response_model=SettlementReceiptOut,
    dependencies=[Depends(require_roles("admin"))],
)
def issue_settlement_receipt(
    settlement_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    settlement = get_settlement(db, settlement_id, for_update=True)
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")
    receipt = issue_receipt(db, settlement)
    create_audit_log(
        db,
        action="settlement_receipt_issued",
        entity_type="service_settlement",
        entity_id=settlement.id,
        actor=current_user,
        new_value={"receipt_number": receipt.receipt_number},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    db.commit()
    _send_receipt_email_if_possible(db, settlement, receipt)
    return receipt


@router.get("/{settlement_id}/receipt", response_model=SettlementReceiptOut)
def get_receipt(settlement_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    settlement = get_settlement(db, settlement_id)
    if not settlement:
        raise HTTPException(status_code=404, detail="Settlement not found")
    _enforce_settlement_owner_or_admin(db, settlement, current_user)
    if not settlement.receipts:
        raise HTTPException(status_code=404, detail="Receipt not found")
    return settlement.receipts[-1]
