import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.mailer import (
    send_service_case_notification_email,
    send_service_case_response_email,
)
from app.core.config import settings
from app.core.security import get_current_user, require_roles
from app.crud.audit import (
    create_audit_log,
    create_service_case,
    get_open_service_case_by_appointment_for_client,
    get_service_case,
    list_eligible_service_case_appointments,
    list_service_cases,
    list_service_cases_by_client,
    update_service_case,
)
from app.crud.professional import get_professional
from app.crud.service import get_service
from app.crud.settlement import get_settlement_by_appointment
from app.db.deps import get_db
from app.models.appointment import Appointment
from app.schemas.audit import (
    EligibleServiceCaseAppointmentOut,
    ServiceCaseCreate,
    ServiceCaseOut,
    ServiceCaseUpdate,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_owned_completed_and_settled_appointment(
    db: Session,
    *,
    appointment_id: int,
    current_user,
) -> Appointment:
    appointment = db.get(Appointment, appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Cita no encontrada")
    is_owner = appointment.client_user_id == current_user.id or (
        appointment.client_user_id is None and appointment.client_email == current_user.email
    )
    if not is_owner:
        raise HTTPException(status_code=403, detail="No puedes registrar PQRS sobre una cita ajena")
    if appointment.status != "completed":
        raise HTTPException(status_code=409, detail="La PQRS solo puede registrarse sobre citas completadas")
    settlement = get_settlement_by_appointment(db, appointment.id)
    if not settlement or settlement.status != "settled":
        raise HTTPException(
            status_code=409,
            detail="La PQRS solo puede registrarse cuando la liquidacion del servicio este cerrada",
        )
    return appointment


def _appointment_context(db: Session, appointment: Appointment) -> dict[str, str]:
    service = get_service(db, appointment.service_id)
    professional = get_professional(db, appointment.professional_id)
    return {
        "service_name": service.name if service else f"Servicio #{appointment.service_id}",
        "professional_name": professional.name if professional else f"Profesional #{appointment.professional_id}",
    }


def _send_service_case_created_email_if_possible(
    db: Session,
    *,
    appointment: Appointment,
    current_user,
    service_case,
) -> None:
    if not settings.smtp_enabled or not settings.PQRS_ADMIN_EMAIL:
        return
    try:
        context = _appointment_context(db, appointment)
        send_service_case_notification_email(
            settings.PQRS_ADMIN_EMAIL,
            client_name=appointment.client_name or current_user.name,
            client_email=appointment.client_email or current_user.email,
            case_type=service_case.case_type,
            subject_line=service_case.subject,
            description=service_case.description,
            appointment_date=appointment.date,
            appointment_time=appointment.time,
            service_name=context["service_name"],
            professional_name=context["professional_name"],
        )
    except Exception:
        logger.exception("No fue posible enviar correo de nueva PQRS al administrador")


def _send_service_case_response_email_if_possible(
    db: Session,
    *,
    appointment: Appointment,
    service_case,
) -> None:
    if not settings.smtp_enabled or not appointment.client_email:
        return
    if not service_case.admin_response:
        return
    try:
        context = _appointment_context(db, appointment)
        send_service_case_response_email(
            appointment.client_email,
            client_name=appointment.client_name,
            case_type=service_case.case_type,
            subject_line=service_case.subject,
            status=service_case.status,
            admin_response=service_case.admin_response,
            service_name=context["service_name"],
            appointment_date=appointment.date,
            appointment_time=appointment.time,
        )
    except Exception:
        logger.exception("No fue posible enviar correo de respuesta PQRS al cliente")


@router.post("/me", response_model=ServiceCaseOut, dependencies=[Depends(require_roles("client"))])
def create_my_service_case(
    payload: ServiceCaseCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    subject = payload.subject.strip()
    description = payload.description.strip()
    if len(subject) < 5:
        raise HTTPException(status_code=422, detail="El asunto debe tener al menos 5 caracteres")
    if len(description) < 15:
        raise HTTPException(status_code=422, detail="La descripcion debe tener al menos 15 caracteres")

    appointment = _get_owned_completed_and_settled_appointment(
        db,
        appointment_id=payload.appointment_id,
        current_user=current_user,
    )

    existing = get_open_service_case_by_appointment_for_client(
        db,
        appointment_id=appointment.id,
        client_user_id=current_user.id,
    )
    if existing:
        raise HTTPException(status_code=409, detail="Ya tienes una PQRS abierta para esta cita")

    service_case = create_service_case(
        db,
        appointment_id=appointment.id,
        client_user_id=current_user.id,
        case_type=payload.case_type,
        subject=subject,
        description=description,
    )
    create_audit_log(
        db,
        action="service_case_created",
        entity_type="service_case",
        entity_id=service_case.id,
        actor=current_user,
        new_value={
            "appointment_id": appointment.id,
            "case_type": service_case.case_type,
            "status": service_case.status,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    _send_service_case_created_email_if_possible(
        db,
        appointment=appointment,
        current_user=current_user,
        service_case=service_case,
    )
    return service_case


@router.get("/my", response_model=list[ServiceCaseOut], dependencies=[Depends(require_roles("client"))])
def list_my_service_cases(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return list_service_cases_by_client(db, current_user.id)


@router.get(
    "/my/eligible-appointments",
    response_model=list[EligibleServiceCaseAppointmentOut],
    dependencies=[Depends(require_roles("client"))],
)
def list_my_eligible_service_case_appointments(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    rows = list_eligible_service_case_appointments(
        db,
        client_user_id=current_user.id,
        client_email=current_user.email,
    )
    return [
        EligibleServiceCaseAppointmentOut(
            id=appointment.id,
            service_id=appointment.service_id,
            professional_id=appointment.professional_id,
            date=appointment.date,
            time=appointment.time,
            status=appointment.status,
            settlement_id=settlement.id,
            total_amount=settlement.total_amount,
            deposit_amount=settlement.deposit_amount,
            paid_amount=settlement.paid_amount,
        )
        for appointment, settlement in rows
    ]


@router.get("", response_model=list[ServiceCaseOut], dependencies=[Depends(require_roles("admin"))])
def list_all_service_cases(
    status: str | None = None,
    case_type: str | None = None,
    db: Session = Depends(get_db),
):
    return list_service_cases(db, status=status, case_type=case_type)


@router.get("/{case_id}", response_model=ServiceCaseOut)
def get_one_service_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service_case = get_service_case(db, case_id)
    if not service_case:
        raise HTTPException(status_code=404, detail="PQRS no encontrada")
    if current_user.role != "admin" and service_case.client_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes acceso a esta PQRS")
    return service_case


@router.post("/{case_id}/review", response_model=ServiceCaseOut, dependencies=[Depends(require_roles("admin"))])
def review_service_case(
    case_id: int,
    payload: ServiceCaseUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    service_case = get_service_case(db, case_id)
    if not service_case:
        raise HTTPException(status_code=404, detail="PQRS no encontrada")
    if payload.status in {"resolved", "closed", "rejected"} and not (payload.admin_response or "").strip():
        raise HTTPException(status_code=422, detail="Debes registrar una respuesta administrativa para cerrar la PQRS")

    old_value = {
        "status": service_case.status,
        "admin_response": service_case.admin_response,
    }
    updated = update_service_case(
        db,
        service_case,
        status=payload.status,
        admin_response=payload.admin_response,
        reviewed_by_user_id=current_user.id,
    )
    create_audit_log(
        db,
        action="service_case_reviewed",
        entity_type="service_case",
        entity_id=updated.id,
        actor=current_user,
        old_value=old_value,
        new_value={
            "status": updated.status,
            "admin_response": updated.admin_response,
            "reviewed_by_user_id": updated.reviewed_by_user_id,
        },
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    appointment = db.get(Appointment, updated.appointment_id)
    if appointment:
        _send_service_case_response_email_if_possible(
            db,
            appointment=appointment,
            service_case=updated,
        )
    return updated
