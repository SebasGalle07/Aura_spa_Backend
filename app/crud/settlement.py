from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.appointment import Appointment
from app.models.settlement import ServiceSettlement, SettlementPayment, SettlementReceipt


def get_settlement(db: Session, settlement_id: int, for_update: bool = False):
    stmt = (
        select(ServiceSettlement)
        .options(
            selectinload(ServiceSettlement.payments),
            selectinload(ServiceSettlement.receipts),
        )
        .where(ServiceSettlement.id == settlement_id)
    )
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def get_settlement_by_appointment(db: Session, appointment_id: int, for_update: bool = False):
    stmt = select(ServiceSettlement).where(ServiceSettlement.appointment_id == appointment_id)
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def list_settlements(
    db: Session,
    status: str | None = None,
    appointment_id: int | None = None,
    service_id: int | None = None,
    client_user_id: int | None = None,
):
    stmt = select(ServiceSettlement).order_by(ServiceSettlement.created_at.desc(), ServiceSettlement.id.desc())
    if status:
        stmt = stmt.where(ServiceSettlement.status == status)
    if appointment_id:
        stmt = stmt.where(ServiceSettlement.appointment_id == appointment_id)
    if service_id:
        stmt = stmt.where(ServiceSettlement.service_id == service_id)
    if client_user_id:
        stmt = stmt.where(ServiceSettlement.client_user_id == client_user_id)
    return list(db.scalars(stmt).all())


def list_settlements_by_client(db: Session, user_id: int, email: str):
    stmt = (
        select(ServiceSettlement)
        .join(Appointment, ServiceSettlement.appointment_id == Appointment.id)
        .where(
            or_(
                ServiceSettlement.client_user_id == user_id,
                Appointment.client_email == email,
            )
        )
        .order_by(ServiceSettlement.created_at.desc(), ServiceSettlement.id.desc())
    )
    return list(db.scalars(stmt).all())


def create_settlement(db: Session, data: dict):
    settlement = ServiceSettlement(**data)
    db.add(settlement)
    db.flush()
    return settlement


def update_settlement(db: Session, settlement: ServiceSettlement, data: dict):
    for field, value in data.items():
        setattr(settlement, field, value)
    db.add(settlement)
    db.flush()
    return settlement


def create_settlement_payment(db: Session, data: dict):
    payment = SettlementPayment(**data)
    db.add(payment)
    db.flush()
    return payment


def create_settlement_receipt(db: Session, data: dict):
    receipt = SettlementReceipt(**data)
    db.add(receipt)
    db.flush()
    return receipt
