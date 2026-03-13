import logging
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.mailer import send_appointment_confirmation_email
from app.core.security import get_current_user, require_roles
from app.core.specialty_match import is_professional_compatible_with_service
from app.crud.appointment import (
    add_history,
    add_status_log,
    get_appointment,
    get_appointment_for_update,
    get_payment_by_reference,
    list_appointments,
    list_appointments_by_client,
    list_payments_by_appointment,
    update_appointment,
)
from app.crud.professional import get_professional
from app.crud.service import get_service
from app.db.deps import get_db
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentNotes,
    AppointmentOut,
    AppointmentPaymentInit,
    AppointmentPaymentInitResponse,
    AppointmentPaymentOut,
    AppointmentReschedule,
    PaymentWebhookPayload,
    PaymentWebhookResponse,
)
from app.services.reservation_workflow import (
    apply_payment_webhook,
    cancel_appointment,
    complete_appointment,
    expire_pending_appointments,
    get_checkout_url,
    initialize_payment_for_appointment,
    lock_slot_and_validate,
    prepare_pending_appointment_data,
    reschedule_appointment,
)
from app.crud.appointment import create_appointment

router = APIRouter()
logger = logging.getLogger(__name__)


def _resolve_actor(current_user) -> tuple[str, int | None]:
    if not current_user:
        return "system", None
    return current_user.role, current_user.id


def _enforce_owner_or_admin(appointment, current_user):
    if current_user.role == "admin":
        return
    if appointment.client_user_id is not None and appointment.client_user_id == current_user.id:
        return
    if appointment.client_email == current_user.email:
        return
    raise HTTPException(status_code=403, detail="Not enough permissions")


@router.post("", response_model=AppointmentOut, dependencies=[Depends(require_roles("client", "admin"))])
def create_one(payload: AppointmentCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    expire_pending_appointments(db)

    service = get_service(db, payload.service_id)
    professional = get_professional(db, payload.professional_id)
    if not service or not professional:
        raise HTTPException(status_code=404, detail="Service or professional not found")
    if not is_professional_compatible_with_service(service.category, professional.specialty):
        raise HTTPException(status_code=422, detail="El profesional seleccionado no presta este servicio")

    lock_slot_and_validate(
        db,
        professional_id=payload.professional_id,
        date=payload.date,
        time=payload.time,
        service_duration=service.duration,
    )

    client_name = payload.client_name or current_user.name
    client_email = payload.client_email or current_user.email
    client_phone = payload.client_phone or current_user.phone
    data = prepare_pending_appointment_data(
        service,
        client_user_id=current_user.id if current_user.role == "client" else None,
        client_name=client_name,
        client_email=client_email,
        client_phone=client_phone,
        professional_id=payload.professional_id,
        date=payload.date,
        time=payload.time,
        notes=payload.notes,
    )

    try:
        appointment = create_appointment(db, data)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El horario ya fue reservado")

    add_history(appointment, "Reserva creada. Pendiente de pago")
    add_status_log(
        db,
        appointment_id=appointment.id,
        from_status=None,
        to_status=appointment.status,
        reason="Reserva creada y cupo bloqueado temporalmente",
        actor_type=current_user.role,
        actor_id=current_user.id,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.get("/my", response_model=list[AppointmentOut], dependencies=[Depends(require_roles("client"))])
def my_appointments(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    expire_pending_appointments(db, commit=True)
    return list_appointments_by_client(db, current_user.id, current_user.email)


@router.get("", response_model=list[AppointmentOut], dependencies=[Depends(require_roles("admin"))])
def list_all(
    date: str | None = None,
    status: str | None = None,
    service_id: int | None = None,
    professional_id: int | None = None,
    db: Session = Depends(get_db),
):
    expire_pending_appointments(db, commit=True)
    return list_appointments(
        db,
        date=date,
        status=status,
        service_id=service_id,
        professional_id=professional_id,
    )


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_one(appointment_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    expire_pending_appointments(db, commit=True)
    appointment = get_appointment(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _enforce_owner_or_admin(appointment, current_user)
    return appointment


@router.post(
    "/{appointment_id}/payments/init",
    response_model=AppointmentPaymentInitResponse,
    dependencies=[Depends(require_roles("client", "admin"))],
)
def init_payment(
    appointment_id: int,
    payload: AppointmentPaymentInit | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    expire_pending_appointments(db, commit=True)
    appointment = get_appointment_for_update(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _enforce_owner_or_admin(appointment, current_user)

    payment = initialize_payment_for_appointment(db, appointment, method=payload.method if payload else None)
    update_appointment(
        db,
        appointment,
        {
            "payment_reference": payment.provider_reference,
            "payment_provider": payment.provider,
            "payment_method": payment.method,
        },
    )
    db.commit()
    return {
        "appointment_id": appointment.id,
        "payment_reference": payment.provider_reference,
        "provider": payment.provider,
        "amount": payment.amount,
        "currency": payment.currency,
        "payment_due_at": appointment.payment_due_at,
        "status": payment.status,
        "checkout_url": get_checkout_url(payment),
    }


@router.get(
    "/{appointment_id}/payments",
    response_model=list[AppointmentPaymentOut],
    dependencies=[Depends(require_roles("client", "admin"))],
)
def list_appointment_payments(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    appointment = get_appointment(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _enforce_owner_or_admin(appointment, current_user)
    return list_payments_by_appointment(db, appointment_id)


@router.post("/payments/webhook", response_model=PaymentWebhookResponse)
def payment_webhook(
    payload: PaymentWebhookPayload,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
    db: Session = Depends(get_db),
):
    if settings.PAYMENT_WEBHOOK_SECRET and x_webhook_secret != settings.PAYMENT_WEBHOOK_SECRET:
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

    payment = get_payment_by_reference(db, payload.provider_reference, for_update=True)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment reference not found")
    appointment = get_appointment_for_update(db, payment.appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appointment = apply_payment_webhook(
        db,
        payment=payment,
        appointment=appointment,
        provider_tx_id=payload.provider_tx_id,
        status=payload.status,
        method=payload.method,
        amount=payload.amount,
        metadata=payload.metadata,
    )
    db.commit()
    db.refresh(appointment)

    if appointment.status == "confirmed" and payload.status == "approved":
        service = get_service(db, appointment.service_id)
        professional = get_professional(db, appointment.professional_id)
        if settings.smtp_enabled and service and professional and appointment.client_email:
            try:
                send_appointment_confirmation_email(
                    to_email=appointment.client_email,
                    client_name=appointment.client_name,
                    service_name=service.name,
                    professional_name=professional.name,
                    date=appointment.date,
                    time=appointment.time,
                    notes=appointment.notes,
                )
            except Exception:
                logger.exception("No fue posible enviar correo de confirmacion para cita %s", appointment.id)

    return {
        "ok": True,
        "appointment_id": appointment.id,
        "appointment_status": appointment.status,
        "payment_status": appointment.payment_status,
    }


@router.post(
    "/{appointment_id}/payments/mock-approve",
    response_model=AppointmentOut,
    dependencies=[Depends(require_roles("client", "admin"))],
)
def mock_approve_payment(
    appointment_id: int,
    payload: AppointmentPaymentInit | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    appointment = get_appointment_for_update(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _enforce_owner_or_admin(appointment, current_user)

    payment = initialize_payment_for_appointment(db, appointment, method=payload.method if payload else "mock_card")
    appointment = apply_payment_webhook(
        db,
        payment=payment,
        appointment=appointment,
        provider_tx_id=f"MOCK-{uuid4().hex[:12].upper()}",
        status="approved",
        method=payment.method or "mock_card",
        amount=payment.amount,
        metadata={"source": "mock_approve"},
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/{appointment_id}/confirm", response_model=AppointmentOut, dependencies=[Depends(require_roles("admin"))])
def confirm(appointment_id: int, payload: AppointmentNotes | None = None, db: Session = Depends(get_db)):
    appointment = get_appointment_for_update(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.payment_status != "approved":
        raise HTTPException(status_code=409, detail="La reserva solo puede confirmarse tras pago aprobado")

    previous_status = appointment.status
    updates: dict = {"status": "confirmed"}
    if payload and payload.notes is not None:
        updates["notes"] = payload.notes
    appointment = update_appointment(db, appointment, updates)
    add_history(appointment, "Reserva confirmada por administrador")
    add_status_log(
        db,
        appointment_id=appointment.id,
        from_status=previous_status,
        to_status="confirmed",
        reason="Confirmacion manual de administrador",
        actor_type="admin",
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel(
    appointment_id: int,
    payload: AppointmentNotes | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    appointment = get_appointment_for_update(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _enforce_owner_or_admin(appointment, current_user)
    actor_type, actor_id = _resolve_actor(current_user)
    appointment = cancel_appointment(
        db,
        appointment,
        actor_type=actor_type,
        actor_id=actor_id,
        reason=payload.notes if payload else None,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post(
    "/{appointment_id}/attend",
    response_model=AppointmentOut,
    dependencies=[Depends(require_roles("admin", "professional"))],
)
def attend(
    appointment_id: int,
    payload: AppointmentNotes | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    appointment = get_appointment_for_update(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    actor_type, actor_id = _resolve_actor(current_user)
    appointment = complete_appointment(
        db,
        appointment,
        actor_type=actor_type,
        actor_id=actor_id,
        reason=payload.notes if payload else None,
    )
    db.commit()
    db.refresh(appointment)
    return appointment


@router.post(
    "/{appointment_id}/complete",
    response_model=AppointmentOut,
    dependencies=[Depends(require_roles("admin", "professional"))],
)
def complete(
    appointment_id: int,
    payload: AppointmentNotes | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return attend(appointment_id=appointment_id, payload=payload, db=db, current_user=current_user)


@router.post("/{appointment_id}/reschedule", response_model=AppointmentOut)
def reschedule(
    appointment_id: int,
    payload: AppointmentReschedule,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    appointment = get_appointment_for_update(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _enforce_owner_or_admin(appointment, current_user)

    service = get_service(db, appointment.service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    actor_type, actor_id = _resolve_actor(current_user)
    try:
        appointment = reschedule_appointment(
            db,
            appointment,
            service_duration=service.duration,
            new_date=payload.date,
            new_time=payload.time,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=payload.reason,
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="El horario seleccionado no esta disponible")

    db.commit()
    db.refresh(appointment)
    return appointment


@router.post("/expire-pending", dependencies=[Depends(require_roles("admin"))])
def expire_pending(db: Session = Depends(get_db)):
    expired = expire_pending_appointments(db, commit=True)
    return {"expired": expired}
