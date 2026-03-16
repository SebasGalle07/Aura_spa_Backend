from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.reservation_rules import (
    APPOINTMENT_CANCELLED,
    APPOINTMENT_COMPLETED,
    APPOINTMENT_CONFIRMED,
    APPOINTMENT_EXPIRED,
    APPOINTMENT_PENDING_PAYMENT,
    APPOINTMENT_RESCHEDULED,
    CANCELLABLE_STATUSES,
    COMPLETABLE_STATUSES,
    PAYMENT_APPROVED,
    PAYMENT_CANCELLED,
    PAYMENT_EXPIRED,
    PAYMENT_PENDING,
    PAYMENT_REJECTED,
    PAYABLE_RESERVATION_STATUSES,
    REPROGRAMMABLE_STATUSES,
    compute_deposit_amount,
    compute_payment_due_at,
    current_business_datetime,
    has_minimum_booking_notice,
    has_minimum_reschedule_notice,
    is_future_slot,
)
from app.crud.appointment import (
    acquire_professional_day_lock,
    add_history,
    add_status_log,
    create_payment,
    create_reschedule_event,
    get_payment_by_tx_id,
    get_pending_payment_by_appointment,
    is_slot_blocked,
    list_appointments_by_professional_and_date_with_duration,
    list_expirable_pending,
    update_appointment,
    update_payment,
)
from app.models.appointment import Appointment, Payment
from app.models.service import Service
from app.services.payment_gateway import ensure_wompi_checkout_configured


def _to_minutes(time_str: str) -> int:
    hours, minutes = [int(x) for x in time_str.split(":")]
    return hours * 60 + minutes


def _ensure_slot_available(
    db: Session,
    professional_id: int,
    date: str,
    time: str,
    duration: int,
    exclude_appointment_id: int | None = None,
):
    existing = list_appointments_by_professional_and_date_with_duration(
        db,
        professional_id=professional_id,
        date=date,
        for_update=True,
    )

    requested_start = _to_minutes(time)
    requested_end = requested_start + duration

    for appointment, existing_duration in existing:
        if exclude_appointment_id is not None and appointment.id == exclude_appointment_id:
            continue
        if not is_slot_blocked(appointment):
            continue
        occupied_start = _to_minutes(appointment.time)
        occupied_end = occupied_start + (existing_duration or duration)
        if requested_start < occupied_end and occupied_start < requested_end:
            raise HTTPException(status_code=409, detail="El horario no esta disponible")


def expire_pending_appointments(db: Session, now: datetime | None = None, commit: bool = False) -> int:
    reference_time = current_business_datetime(now)
    expirable = list_expirable_pending(db, reference_time)
    for appointment in expirable:
        from_status = appointment.status
        update_appointment(
            db,
            appointment,
            {
                "status": APPOINTMENT_EXPIRED,
                "payment_status": PAYMENT_EXPIRED,
            },
        )
        add_history(appointment, "Reserva expirada por falta de pago")
        add_status_log(
            db,
            appointment_id=appointment.id,
            from_status=from_status,
            to_status=APPOINTMENT_EXPIRED,
            reason="No se recibio pago dentro del tiempo limite",
            actor_type="system",
        )
    if commit and expirable:
        db.commit()
    return len(expirable)


def prepare_pending_appointment_data(
    service: Service,
    *,
    client_user_id: int | None,
    client_name: str,
    client_email: str,
    client_phone: str | None,
    professional_id: int,
    date: str,
    time: str,
    notes: str | None = "",
) -> dict:
    if not is_future_slot(date, time):
        raise HTTPException(status_code=422, detail="La reserva debe programarse en una fecha y hora futura")
    if not has_minimum_booking_notice(date, time):
        raise HTTPException(
            status_code=422,
            detail=f"La reserva debe realizarse con al menos {settings.RESERVATION_MIN_LEAD_HOURS} horas de anticipacion",
        )

    deposit_amount = compute_deposit_amount(service.price)
    total_price = Decimal(str(service.price))
    balance_amount = max(total_price - deposit_amount, Decimal("0"))

    return {
        "client_user_id": client_user_id,
        "client_name": client_name,
        "client_email": client_email,
        "client_phone": client_phone,
        "service_id": service.id,
        "professional_id": professional_id,
        "date": date,
        "time": time,
        "status": APPOINTMENT_PENDING_PAYMENT,
        "payment_status": PAYMENT_PENDING,
        "payment_due_at": compute_payment_due_at(),
        "deposit_amount": deposit_amount,
        "balance_amount": balance_amount,
        "paid_amount": Decimal("0"),
        "notes": notes or "",
        "history": [],
    }


def lock_slot_and_validate(
    db: Session,
    *,
    professional_id: int,
    date: str,
    time: str,
    service_duration: int,
    exclude_appointment_id: int | None = None,
):
    acquire_professional_day_lock(db, professional_id, date)
    _ensure_slot_available(
        db,
        professional_id=professional_id,
        date=date,
        time=time,
        duration=service_duration,
        exclude_appointment_id=exclude_appointment_id,
    )


def initialize_payment_for_appointment(
    db: Session,
    appointment: Appointment,
    *,
    method: str | None = None,
) -> Payment:
    if settings.PAYMENT_PROVIDER.lower() == "wompi":
        ensure_wompi_checkout_configured()

    if appointment.status not in PAYABLE_RESERVATION_STATUSES:
        raise HTTPException(status_code=409, detail="La reserva no esta disponible para pago")

    if appointment.payment_due_at and appointment.payment_due_at <= current_business_datetime():
        raise HTTPException(status_code=409, detail="La reserva ya expiro por tiempo limite de pago")

    pending = get_pending_payment_by_appointment(db, appointment.id)
    if pending:
        if method:
            pending = update_payment(db, pending, {"method": method})
        return pending

    reference = f"RSV-{appointment.id}-{uuid4().hex[:10].upper()}"
    metadata = {"appointment_id": appointment.id}
    return create_payment(
        db,
        appointment_id=appointment.id,
        amount=appointment.deposit_amount,
        reference=reference,
        provider=settings.PAYMENT_PROVIDER,
        method=method,
        status=PAYMENT_PENDING,
        metadata_json=metadata,
    )


def get_checkout_url(payment: Payment) -> str:
    base = settings.PAYMENT_MOCK_CHECKOUT_BASE_URL.rstrip("/")
    return f"{base}/payments/mock-checkout?reference={payment.provider_reference}"


def apply_payment_webhook(
    db: Session,
    *,
    payment: Payment,
    appointment: Appointment,
    provider_tx_id: str,
    status: str,
    method: str | None = None,
    amount: Decimal | None = None,
    metadata: dict | None = None,
) -> Appointment:
    existing_with_tx = get_payment_by_tx_id(db, provider_tx_id)
    if existing_with_tx and existing_with_tx.id != payment.id:
        raise HTTPException(status_code=409, detail="Referencia de transaccion duplicada")

    if payment.status == PAYMENT_APPROVED:
        return appointment

    update_payload: dict = {
        "status": status,
        "provider_tx_id": provider_tx_id,
        "method": method or payment.method,
        "metadata_json": metadata or payment.metadata_json,
    }
    if amount is not None:
        update_payload["amount"] = amount
    if status == PAYMENT_APPROVED:
        update_payload["paid_at"] = current_business_datetime()
    payment = update_payment(db, payment, update_payload)

    if status == PAYMENT_APPROVED:
        if appointment.status == APPOINTMENT_PENDING_PAYMENT and (
            appointment.payment_due_at is None or appointment.payment_due_at > current_business_datetime()
        ):
            previous_status = appointment.status
            paid_amount = max(Decimal(str(payment.amount)), Decimal(str(appointment.paid_amount or 0)))
            update_appointment(
                db,
                appointment,
                {
                    "status": APPOINTMENT_CONFIRMED,
                    "payment_status": PAYMENT_APPROVED,
                    "paid_amount": paid_amount,
                    "paid_at": payment.paid_at,
                    "payment_reference": payment.provider_reference,
                    "payment_transaction_id": payment.provider_tx_id,
                    "payment_method": payment.method,
                    "payment_provider": payment.provider,
                },
            )
            add_status_log(
                db,
                appointment_id=appointment.id,
                from_status=previous_status,
                to_status=APPOINTMENT_CONFIRMED,
                reason="Pago de anticipo aprobado",
                actor_type="system",
                metadata_json={"payment_reference": payment.provider_reference},
            )
            add_history(appointment, "Pago aprobado. Reserva confirmada")
            return appointment

        if appointment.status == APPOINTMENT_PENDING_PAYMENT:
            previous_status = appointment.status
            update_appointment(
                db,
                appointment,
                {
                    "status": APPOINTMENT_EXPIRED,
                    "payment_status": PAYMENT_APPROVED,
                    "payment_reference": payment.provider_reference,
                    "payment_transaction_id": payment.provider_tx_id,
                    "payment_method": payment.method,
                    "payment_provider": payment.provider,
                },
            )
            add_status_log(
                db,
                appointment_id=appointment.id,
                from_status=previous_status,
                to_status=APPOINTMENT_EXPIRED,
                reason="Pago aprobado fuera del tiempo de retencion",
                actor_type="system",
            )
            add_history(appointment, "Pago aprobado fuera de tiempo. Reserva expirada")
            return appointment

        update_appointment(db, appointment, {"payment_status": PAYMENT_APPROVED})
        add_history(appointment, "Pago aprobado")
        return appointment

    if appointment.payment_status != PAYMENT_APPROVED:
        if status in {PAYMENT_REJECTED, PAYMENT_EXPIRED, PAYMENT_CANCELLED}:
            update_appointment(db, appointment, {"payment_status": status})
            add_history(appointment, f"Pago actualizado a {status}")

    return appointment


def cancel_appointment(
    db: Session,
    appointment: Appointment,
    *,
    actor_type: str,
    actor_id: int | None = None,
    reason: str | None = None,
) -> Appointment:
    if appointment.status not in CANCELLABLE_STATUSES:
        raise HTTPException(status_code=409, detail="La reserva no puede cancelarse en su estado actual")
    if not is_future_slot(appointment.date, appointment.time):
        raise HTTPException(status_code=409, detail="No puedes cancelar una reserva cuya fecha y hora ya pasaron")

    previous_status = appointment.status
    next_payment_status = appointment.payment_status
    metadata: dict = {}
    if appointment.payment_status == PAYMENT_PENDING:
        next_payment_status = PAYMENT_CANCELLED
    elif appointment.payment_status == PAYMENT_APPROVED:
        metadata["deposit_non_refundable"] = True
        metadata["deposit_amount"] = str(appointment.deposit_amount)

    update_appointment(
        db,
        appointment,
        {
            "status": APPOINTMENT_CANCELLED,
            "payment_status": next_payment_status,
            "cancelled_at": current_business_datetime(),
        },
    )
    add_history(appointment, "Reserva cancelada")
    add_status_log(
        db,
        appointment_id=appointment.id,
        from_status=previous_status,
        to_status=APPOINTMENT_CANCELLED,
        reason=reason or "Cancelada por usuario",
        actor_type=actor_type,
        actor_id=actor_id,
        metadata_json=metadata or None,
    )
    return appointment


def reschedule_appointment(
    db: Session,
    appointment: Appointment,
    *,
    service_duration: int,
    new_date: str,
    new_time: str,
    actor_type: str,
    actor_id: int | None = None,
    reason: str | None = None,
) -> Appointment:
    if appointment.status not in REPROGRAMMABLE_STATUSES:
        raise HTTPException(status_code=409, detail="Solo reservas confirmadas pueden reprogramarse")
    if appointment.payment_status != PAYMENT_APPROVED or Decimal(str(appointment.paid_amount or 0)) <= Decimal("0"):
        raise HTTPException(status_code=409, detail="La reserva debe tener pago aprobado para reprogramarse")
    if not has_minimum_reschedule_notice(appointment.date, appointment.time):
        raise HTTPException(status_code=409, detail="La reprogramacion requiere al menos 48 horas de anticipacion")
    if not is_future_slot(new_date, new_time):
        raise HTTPException(status_code=422, detail="La nueva fecha y hora deben ser futuras")
    if not has_minimum_booking_notice(new_date, new_time):
        raise HTTPException(
            status_code=422,
            detail=f"La nueva fecha debe tener al menos {settings.RESERVATION_MIN_LEAD_HOURS} horas de anticipacion",
        )

    lock_dates = {appointment.date, new_date}
    for lock_date in sorted(lock_dates):
        acquire_professional_day_lock(db, appointment.professional_id, lock_date)

    _ensure_slot_available(
        db,
        professional_id=appointment.professional_id,
        date=new_date,
        time=new_time,
        duration=service_duration,
        exclude_appointment_id=appointment.id,
    )

    previous_status = appointment.status
    old_date = appointment.date
    old_time = appointment.time
    update_appointment(
        db,
        appointment,
        {
            "date": new_date,
            "time": new_time,
            "status": APPOINTMENT_RESCHEDULED,
        },
    )
    create_reschedule_event(
        db,
        appointment_id=appointment.id,
        old_date=old_date,
        old_time=old_time,
        new_date=new_date,
        new_time=new_time,
        reason=reason,
        actor_type=actor_type,
        actor_id=actor_id,
    )
    add_status_log(
        db,
        appointment_id=appointment.id,
        from_status=previous_status,
        to_status=APPOINTMENT_RESCHEDULED,
        reason=reason or "Reserva reprogramada",
        actor_type=actor_type,
        actor_id=actor_id,
        metadata_json={
            "old_date": old_date,
            "old_time": old_time,
            "new_date": new_date,
            "new_time": new_time,
        },
    )
    add_history(appointment, f"Reserva reprogramada a {new_date} {new_time}")
    return appointment


def process_mock_payment_result(
    db: Session,
    *,
    payment: Payment,
    appointment: Appointment,
    status: str,
    method: str | None = None,
) -> Appointment:
    if status not in {PAYMENT_APPROVED, PAYMENT_REJECTED, PAYMENT_EXPIRED, PAYMENT_CANCELLED}:
        raise HTTPException(status_code=422, detail="Estado de pago simulado no valido")

    return apply_payment_webhook(
        db,
        payment=payment,
        appointment=appointment,
        provider_tx_id=f"MOCK-{status.upper()}-{uuid4().hex[:12].upper()}",
        status=status,
        method=method or "mock_card",
        amount=payment.amount,
        metadata={"source": "mock_checkout"},
    )


def complete_appointment(
    db: Session,
    appointment: Appointment,
    *,
    actor_type: str,
    actor_id: int | None = None,
    reason: str | None = None,
) -> Appointment:
    if appointment.status not in COMPLETABLE_STATUSES:
        raise HTTPException(status_code=409, detail="La reserva no puede marcarse como completada")

    previous_status = appointment.status
    update_appointment(db, appointment, {"status": APPOINTMENT_COMPLETED})
    add_history(appointment, "Servicio completado")
    add_status_log(
        db,
        appointment_id=appointment.id,
        from_status=previous_status,
        to_status=APPOINTMENT_COMPLETED,
        reason=reason or "Servicio atendido y completado",
        actor_type=actor_type,
        actor_id=actor_id,
    )
    return appointment
