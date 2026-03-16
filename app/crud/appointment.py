from datetime import datetime
from decimal import Decimal
import zlib

from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from app.core.reservation_rules import ACTIVE_BLOCKING_STATUSES, APPOINTMENT_PENDING_PAYMENT, current_business_datetime
from app.models.appointment import Appointment, AppointmentReschedule, AppointmentStatusLog, Payment
from app.models.service import Service


def list_appointments(
    db: Session,
    date: str | None = None,
    status: str | None = None,
    service_id: int | None = None,
    professional_id: int | None = None,
    client_email: str | None = None,
):
    stmt = select(Appointment)
    if date:
        stmt = stmt.where(Appointment.date == date)
    if status:
        stmt = stmt.where(Appointment.status == status)
    if service_id:
        stmt = stmt.where(Appointment.service_id == service_id)
    if professional_id:
        stmt = stmt.where(Appointment.professional_id == professional_id)
    if client_email:
        stmt = stmt.where(Appointment.client_email == client_email)
    stmt = stmt.order_by(Appointment.date.desc(), Appointment.time.desc(), Appointment.id.desc())
    return list(db.scalars(stmt).all())


def list_appointments_by_client(db: Session, user_id: int, email: str):
    stmt = (
        select(Appointment)
        .where(
            or_(
                Appointment.client_user_id == user_id,
                and_(
                    Appointment.client_user_id.is_(None),
                    Appointment.client_email == email,
                ),
            )
        )
        .order_by(Appointment.date.desc(), Appointment.time.desc(), Appointment.id.desc())
    )
    return list(db.scalars(stmt).all())


def list_appointments_by_professional_and_date_with_duration(
    db: Session,
    professional_id: int,
    date: str,
    for_update: bool = False,
):
    stmt = (
        select(Appointment, Service.duration)
        .join(Service, Appointment.service_id == Service.id)
        .where(
            Appointment.professional_id == professional_id,
            Appointment.date == date,
        )
    )
    if for_update:
        stmt = stmt.with_for_update()
    return list(db.execute(stmt).all())


def list_expirable_pending(db: Session, now: datetime):
    stmt = select(Appointment).where(
        Appointment.status == APPOINTMENT_PENDING_PAYMENT,
        Appointment.payment_due_at.is_not(None),
        Appointment.payment_due_at <= now,
    )
    return list(db.scalars(stmt).all())


def get_appointment(db: Session, appointment_id: int):
    return db.get(Appointment, appointment_id)


def get_appointment_for_update(db: Session, appointment_id: int):
    return db.scalar(select(Appointment).where(Appointment.id == appointment_id).with_for_update())


def create_appointment(db: Session, data: dict):
    obj = Appointment(**data)
    db.add(obj)
    db.flush()
    return obj


def update_appointment(db: Session, db_obj: Appointment, data: dict):
    for field, value in data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    db.flush()
    return db_obj


def add_history(db_obj: Appointment, action: str):
    history = list(db_obj.history or [])
    history.append({"action": action, "at": current_business_datetime().isoformat(timespec="minutes")})
    db_obj.history = history


def add_status_log(
    db: Session,
    appointment_id: int,
    from_status: str | None,
    to_status: str,
    reason: str | None = None,
    actor_type: str = "system",
    actor_id: int | None = None,
    metadata_json: dict | None = None,
):
    log = AppointmentStatusLog(
        appointment_id=appointment_id,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        actor_type=actor_type,
        actor_id=actor_id,
        metadata_json=metadata_json,
    )
    db.add(log)
    db.flush()
    return log


def create_reschedule_event(
    db: Session,
    appointment_id: int,
    old_date: str,
    old_time: str,
    new_date: str,
    new_time: str,
    reason: str | None = None,
    actor_type: str = "system",
    actor_id: int | None = None,
):
    event = AppointmentReschedule(
        appointment_id=appointment_id,
        old_date=old_date,
        old_time=old_time,
        new_date=new_date,
        new_time=new_time,
        reason=reason,
        actor_type=actor_type,
        actor_id=actor_id,
    )
    db.add(event)
    db.flush()
    return event


def create_payment(
    db: Session,
    appointment_id: int,
    amount: Decimal,
    reference: str,
    provider: str = "mock",
    method: str | None = None,
    status: str = "pending",
    metadata_json: dict | None = None,
):
    payment = Payment(
        appointment_id=appointment_id,
        provider=provider,
        method=method,
        amount=amount,
        status=status,
        provider_reference=reference,
        metadata_json=metadata_json,
    )
    db.add(payment)
    db.flush()
    return payment


def get_payment_by_reference(db: Session, reference: str, for_update: bool = False):
    stmt = select(Payment).where(Payment.provider_reference == reference)
    if for_update:
        stmt = stmt.with_for_update()
    return db.scalar(stmt)


def get_payment_by_tx_id(db: Session, provider_tx_id: str):
    return db.scalar(select(Payment).where(Payment.provider_tx_id == provider_tx_id))


def list_payments_by_appointment(db: Session, appointment_id: int):
    stmt = select(Payment).where(Payment.appointment_id == appointment_id).order_by(Payment.id.desc())
    return list(db.scalars(stmt).all())


def get_pending_payment_by_appointment(db: Session, appointment_id: int):
    stmt = (
        select(Payment)
        .where(
            Payment.appointment_id == appointment_id,
            Payment.status == "pending",
        )
        .order_by(Payment.id.desc())
        .limit(1)
    )
    return db.scalar(stmt)


def update_payment(db: Session, payment: Payment, data: dict):
    for field, value in data.items():
        setattr(payment, field, value)
    db.add(payment)
    db.flush()
    return payment


def acquire_professional_day_lock(db: Session, professional_id: int, date: str) -> None:
    bind = db.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    key_source = f"appointments:{professional_id}:{date}"
    lock_key = zlib.crc32(key_source.encode("utf-8"))
    db.execute(text("SELECT pg_advisory_xact_lock(:lock_key)"), {"lock_key": lock_key})


def is_slot_blocked(appointment: Appointment, now: datetime | None = None) -> bool:
    now_value = current_business_datetime(now)
    if appointment.status == APPOINTMENT_PENDING_PAYMENT:
        return bool(appointment.payment_due_at and appointment.payment_due_at > now_value)
    return appointment.status in ACTIVE_BLOCKING_STATUSES
