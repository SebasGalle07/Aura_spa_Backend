from datetime import timedelta
from decimal import Decimal

from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now
from app.models.benefit import ClientBenefit

BENEFIT_ACTIVE = "active"
BENEFIT_RESERVED = "reserved"
BENEFIT_USED = "used"
BENEFIT_EXPIRED = "expired"


def _expire_if_needed(db: Session, benefit: ClientBenefit | None) -> ClientBenefit | None:
    if not benefit:
        return None
    if benefit.status in {BENEFIT_ACTIVE, BENEFIT_RESERVED} and benefit.expires_at <= utc_now():
        benefit.status = BENEFIT_EXPIRED
        benefit.reserved_appointment_id = None
        benefit.updated_at = utc_now()
        db.add(benefit)
        db.flush()
    return benefit


def get_any_benefit_for_client(db: Session, client_user_id: int) -> ClientBenefit | None:
    return db.scalar(
        select(ClientBenefit)
        .where(ClientBenefit.client_user_id == client_user_id)
        .order_by(desc(ClientBenefit.created_at))
        .limit(1)
    )


def get_benefit(db: Session, benefit_id: int) -> ClientBenefit | None:
    benefit = db.get(ClientBenefit, benefit_id)
    return _expire_if_needed(db, benefit)


def get_active_or_reserved_benefit_for_client(db: Session, client_user_id: int) -> ClientBenefit | None:
    benefit = db.scalar(
        select(ClientBenefit)
        .where(
            ClientBenefit.client_user_id == client_user_id,
            ClientBenefit.status.in_([BENEFIT_ACTIVE, BENEFIT_RESERVED]),
        )
        .order_by(desc(ClientBenefit.created_at))
        .limit(1)
    )
    return _expire_if_needed(db, benefit)


def get_available_benefit_for_client(db: Session, client_user_id: int) -> ClientBenefit | None:
    benefit = get_active_or_reserved_benefit_for_client(db, client_user_id)
    if not benefit:
        return None
    if benefit.status == BENEFIT_RESERVED and benefit.reserved_appointment_id:
        return None
    return benefit if benefit.status == BENEFIT_ACTIVE else None


def get_benefit_for_appointment(db: Session, appointment_id: int) -> ClientBenefit | None:
    benefit = db.scalar(
        select(ClientBenefit).where(
            or_(
                ClientBenefit.reserved_appointment_id == appointment_id,
                ClientBenefit.used_appointment_id == appointment_id,
            )
        )
    )
    return _expire_if_needed(db, benefit)


def create_benefit_from_service_case(
    db: Session,
    *,
    client_user_id: int,
    source_service_case_id: int,
) -> ClientBenefit:
    now = utc_now()
    benefit = ClientBenefit(
        client_user_id=client_user_id,
        source_service_case_id=source_service_case_id,
        discount_percent=Decimal(str(settings.PQRS_DISCOUNT_PERCENT)),
        status=BENEFIT_ACTIVE,
        granted_at=now,
        expires_at=now + timedelta(days=settings.PQRS_DISCOUNT_DAYS),
    )
    db.add(benefit)
    db.flush()
    return benefit


def reserve_benefit_for_appointment(db: Session, benefit: ClientBenefit, appointment_id: int) -> ClientBenefit:
    benefit = _expire_if_needed(db, benefit)
    if not benefit or benefit.status != BENEFIT_ACTIVE:
        return benefit
    benefit.status = BENEFIT_RESERVED
    benefit.reserved_appointment_id = appointment_id
    benefit.updated_at = utc_now()
    db.add(benefit)
    db.flush()
    return benefit


def use_benefit_for_appointment(db: Session, benefit: ClientBenefit, appointment_id: int) -> ClientBenefit:
    benefit = _expire_if_needed(db, benefit)
    if not benefit or benefit.status not in {BENEFIT_ACTIVE, BENEFIT_RESERVED}:
        return benefit
    benefit.status = BENEFIT_USED
    benefit.used_appointment_id = appointment_id
    benefit.reserved_appointment_id = appointment_id
    benefit.used_at = utc_now()
    benefit.updated_at = utc_now()
    db.add(benefit)
    db.flush()
    return benefit


def release_benefit_for_appointment(db: Session, appointment_id: int) -> ClientBenefit | None:
    benefit = get_benefit_for_appointment(db, appointment_id)
    if not benefit:
        return None
    if benefit.status == BENEFIT_RESERVED and benefit.reserved_appointment_id == appointment_id and not benefit.used_appointment_id:
        benefit.status = BENEFIT_ACTIVE if benefit.expires_at > utc_now() else BENEFIT_EXPIRED
        benefit.reserved_appointment_id = None
        benefit.updated_at = utc_now()
        db.add(benefit)
        db.flush()
    return benefit
