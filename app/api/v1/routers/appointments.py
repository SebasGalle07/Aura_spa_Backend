import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
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
    AppointmentPaymentCheckoutData,
    AppointmentPaymentInitResponse,
    AppointmentPaymentOut,
    AppointmentReschedule,
    MockPaymentResultPayload,
    PaymentSyncResponse,
    PaymentWebhookPayload,
    PaymentWebhookResponse,
)
from app.services.payment_gateway import (
    fetch_wompi_transaction,
    get_checkout_payload,
    map_payu_status,
    map_wompi_transaction_status,
    verify_payu_confirmation_signature,
    verify_wompi_event_signature,
)
from app.monitoring.metrics import observe_appointment_event, observe_appointment_transition
from app.services.reservation_workflow import (
    apply_payment_webhook,
    cancel_appointment,
    complete_appointment,
    expire_pending_appointments,
    initialize_payment_for_appointment,
    lock_slot_and_validate,
    prepare_pending_appointment_data,
    process_mock_payment_result,
    reschedule_appointment,
)
from app.services.settlement_workflow import ensure_settlement_for_appointment
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


def _send_confirmation_email_if_needed(db: Session, appointment, payment_status: str) -> None:
    if appointment.status != "confirmed" or payment_status != "approved":
        return
    service = get_service(db, appointment.service_id)
    professional = get_professional(db, appointment.professional_id)
    if not (settings.smtp_enabled and service and professional and appointment.client_email):
        return
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


def _payment_init_response(appointment, payment) -> dict:
    checkout_url, checkout_data = get_checkout_payload(payment, appointment)
    return {
        "appointment_id": appointment.id,
        "payment_reference": payment.provider_reference,
        "provider": payment.provider,
        "amount": payment.amount,
        "currency": payment.currency,
        "payment_due_at": appointment.payment_due_at,
        "status": payment.status,
        "checkout_url": checkout_url,
        "checkout_data": AppointmentPaymentCheckoutData(**checkout_data) if checkout_data else None,
    }


@router.post("", response_model=AppointmentOut, dependencies=[Depends(require_roles("client"))])
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

    if current_user.role == "client":
        client_name = current_user.name
        client_email = current_user.email
        client_phone = payload.client_phone or current_user.phone
    else:
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
    observe_appointment_event("created", appointment.status)
    observe_appointment_transition(None, appointment.status)
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
    dependencies=[Depends(require_roles("client"))],
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
    return _payment_init_response(appointment, payment)


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


@router.get(
    "/payments/by-reference/{provider_reference}",
    response_model=AppointmentPaymentInitResponse,
    dependencies=[Depends(require_roles("client"))],
)
def get_payment_checkout_data(
    provider_reference: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    expire_pending_appointments(db, commit=True)
    payment = get_payment_by_reference(db, provider_reference)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment reference not found")
    appointment = get_appointment(db, payment.appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _enforce_owner_or_admin(appointment, current_user)
    return _payment_init_response(appointment, payment)


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
    _send_confirmation_email_if_needed(db, appointment, payload.status)

    return {
        "ok": True,
        "appointment_id": appointment.id,
        "appointment_status": appointment.status,
        "payment_status": appointment.payment_status,
    }


@router.api_route("/payments/payu/confirmation", methods=["GET", "POST"], response_model=dict)
async def payu_payment_confirmation(request: Request, db: Session = Depends(get_db)):
    if request.method == "POST":
        form = await request.form()
        payload = dict(form.items())
    else:
        payload = dict(request.query_params.items())

    if not payload:
        raise HTTPException(status_code=400, detail="No se recibio informacion de confirmacion")
    if not verify_payu_confirmation_signature(payload):
        raise HTTPException(status_code=401, detail="Firma de confirmacion invalida")

    reference = str(payload.get("reference_sale") or payload.get("referenceCode") or "").strip()
    state_pol = str(payload.get("state_pol") or payload.get("transactionState") or "").strip()
    provider_tx_id = str(payload.get("transaction_id") or payload.get("transactionId") or "").strip()
    mapped_status = map_payu_status(state_pol)
    if not reference or not provider_tx_id or not mapped_status:
        return {"ok": True, "ignored": True}

    payment = get_payment_by_reference(db, reference, for_update=True)
    if not payment:
        return {"ok": True, "ignored": True}
    appointment = get_appointment_for_update(db, payment.appointment_id)
    if not appointment:
        return {"ok": True, "ignored": True}

    appointment = apply_payment_webhook(
        db,
        payment=payment,
        appointment=appointment,
        provider_tx_id=provider_tx_id,
        status=mapped_status,
        method=str(payload.get("payment_method_name") or payload.get("lapPaymentMethod") or "payu"),
        amount=Decimal(str(payload.get("value") or payload.get("TX_VALUE") or payment.amount)),
        metadata={"source": "payu_confirmation", "payload": payload},
    )
    db.commit()
    db.refresh(appointment)
    _send_confirmation_email_if_needed(db, appointment, mapped_status)
    return {"ok": True}


@router.post("/payments/wompi/webhook", response_model=dict)
async def wompi_payment_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload invalido")
    if not verify_wompi_event_signature(payload):
        raise HTTPException(status_code=401, detail="Firma de evento invalida")
    if payload.get("event") != "transaction.updated":
        return {"ok": True, "ignored": True}

    transaction = ((payload.get("data") or {}).get("transaction") or {})
    reference = transaction.get("reference")
    provider_status = str(transaction.get("status") or "")
    mapped_status = map_wompi_transaction_status(provider_status)
    if not reference or not mapped_status:
        return {"ok": True, "ignored": True}

    payment = get_payment_by_reference(db, reference, for_update=True)
    if not payment:
        return {"ok": True, "ignored": True}
    appointment = get_appointment_for_update(db, payment.appointment_id)
    if not appointment:
        return {"ok": True, "ignored": True}

    appointment = apply_payment_webhook(
        db,
        payment=payment,
        appointment=appointment,
        provider_tx_id=str(transaction.get("id") or ""),
        status=mapped_status,
        method=transaction.get("payment_method_type"),
        amount=(Decimal(str(transaction.get("amount_in_cents") or 0)) / Decimal("100")),
        metadata=payload,
    )
    db.commit()
    db.refresh(appointment)
    _send_confirmation_email_if_needed(db, appointment, mapped_status)
    return {"ok": True}


@router.get(
    "/payments/wompi/transactions/{transaction_id}",
    response_model=PaymentSyncResponse,
    dependencies=[Depends(require_roles("client"))],
)
def sync_wompi_transaction(
    transaction_id: str,
    reference: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    transaction = fetch_wompi_transaction(transaction_id)
    if str(transaction.get("reference") or "") != reference:
        raise HTTPException(status_code=409, detail="La transaccion no coincide con la referencia del pago")

    payment = get_payment_by_reference(db, reference, for_update=True)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment reference not found")
    appointment = get_appointment_for_update(db, payment.appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _enforce_owner_or_admin(appointment, current_user)

    provider_status = str(transaction.get("status") or "")
    mapped_status = map_wompi_transaction_status(provider_status)
    if mapped_status:
        appointment = apply_payment_webhook(
            db,
            payment=payment,
            appointment=appointment,
            provider_tx_id=str(transaction.get("id") or transaction_id),
            status=mapped_status,
            method=transaction.get("payment_method_type"),
            amount=(Decimal(str(transaction.get("amount_in_cents") or 0)) / Decimal("100")),
            metadata={"source": "wompi_sync", "transaction": transaction},
        )
        db.commit()
        db.refresh(appointment)
        _send_confirmation_email_if_needed(db, appointment, mapped_status)
    else:
        db.rollback()
        appointment = get_appointment(db, payment.appointment_id)
        if not appointment:
            raise HTTPException(status_code=404, detail="Appointment not found")

    return {
        "ok": True,
        "provider_reference": payment.provider_reference,
        "provider_transaction_id": str(transaction.get("id") or transaction_id),
        "provider_transaction_status": provider_status,
        "appointment_id": appointment.id,
        "appointment_status": appointment.status,
        "payment_status": appointment.payment_status,
    }


@router.post(
    "/payments/mock-checkout/complete",
    response_model=AppointmentOut,
    dependencies=[Depends(require_roles("client"))],
)
def complete_mock_payment(
    payload: MockPaymentResultPayload,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    expire_pending_appointments(db, commit=True)
    payment = get_payment_by_reference(db, payload.provider_reference, for_update=True)
    if not payment:
        raise HTTPException(status_code=404, detail="Payment reference not found")
    appointment = get_appointment_for_update(db, payment.appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _enforce_owner_or_admin(appointment, current_user)

    appointment = process_mock_payment_result(
        db,
        payment=payment,
        appointment=appointment,
        status=payload.status,
        method=payload.method,
    )
    db.commit()
    db.refresh(appointment)
    _send_confirmation_email_if_needed(db, appointment, payload.status)
    return appointment


@router.post(
    "/{appointment_id}/payments/mock-approve",
    response_model=AppointmentOut,
    dependencies=[Depends(require_roles("client"))],
)
def mock_approve_payment(
    appointment_id: int,
    payload: AppointmentPaymentInit | None = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    appointment = get_appointment(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    _enforce_owner_or_admin(appointment, current_user)
    payment = initialize_payment_for_appointment(db, appointment, method=payload.method if payload else "mock_card")
    db.commit()
    db.refresh(payment)
    return complete_mock_payment(
        payload=MockPaymentResultPayload(
            provider_reference=payment.provider_reference,
            status="approved",
            method=payload.method if payload else "mock_card",
        ),
        db=db,
        current_user=current_user,
    )


@router.post("/{appointment_id}/confirm", response_model=AppointmentOut, dependencies=[Depends(require_roles("admin"))])
def confirm(appointment_id: int, payload: AppointmentNotes | None = None, db: Session = Depends(get_db)):
    appointment = get_appointment_for_update(db, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if appointment.payment_status != "approved":
        raise HTTPException(status_code=409, detail="La reserva solo puede confirmarse tras pago aprobado")
    service = get_service(db, appointment.service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

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
    ensure_settlement_for_appointment(db, appointment, service)
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
