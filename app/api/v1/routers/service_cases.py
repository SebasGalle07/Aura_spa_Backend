from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import get_current_user, require_roles
from app.crud.audit import (
    create_audit_log,
    create_service_case,
    get_open_service_case_by_appointment_for_client,
    get_service_case,
    list_service_cases,
    list_service_cases_by_client,
    update_service_case,
)
from app.crud.settlement import get_settlement_by_appointment
from app.db.deps import get_db
from app.models.appointment import Appointment
from app.schemas.audit import ServiceCaseCreate, ServiceCaseOut, ServiceCaseUpdate

router = APIRouter()


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
    return service_case


@router.get("/my", response_model=list[ServiceCaseOut], dependencies=[Depends(require_roles("client"))])
def list_my_service_cases(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return list_service_cases_by_client(db, current_user.id)


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
    return updated
