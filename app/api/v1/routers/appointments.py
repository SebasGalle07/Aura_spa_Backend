import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.mailer import send_appointment_confirmation_email
from app.core.specialty_match import is_professional_compatible_with_service
from app.core.security import require_roles, get_current_user
from app.db.deps import get_db
from app.crud.service import get_service
from app.crud.professional import get_professional
from app.crud.appointment import (
    list_appointments,
    list_appointments_by_client,
    list_appointments_by_professional_and_date_with_duration,
    get_appointment,
    create_appointment,
    update_appointment,
    add_history,
)
from app.schemas.appointment import AppointmentOut, AppointmentCreate, AppointmentReschedule, AppointmentNotes

router = APIRouter()
logger = logging.getLogger(__name__)


def _to_minutes(time_str: str) -> int:
    h, m = [int(x) for x in time_str.split(":")]
    return h * 60 + m


def _ensure_available(
    db: Session,
    professional_id: int,
    date: str,
    time: str,
    duration: int,
    appointment_id: int | None = None,
):
    existing = list_appointments_by_professional_and_date_with_duration(db, professional_id, date)
    start = _to_minutes(time)
    end = start + duration
    for apt, apt_duration in existing:
        if appointment_id is not None and apt.id == appointment_id:
            continue
        if apt.status == "cancelled":
            continue
        apt_start = _to_minutes(apt.time)
        apt_end = apt_start + (apt_duration or duration)
        if start < apt_end and apt_start < end:
            raise HTTPException(status_code=409, detail="Slot not available")


@router.post("", response_model=AppointmentOut, dependencies=[Depends(require_roles("client", "admin"))])
def create_one(payload: AppointmentCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    svc = get_service(db, payload.service_id)
    pro = get_professional(db, payload.professional_id)
    if not svc or not pro:
        raise HTTPException(status_code=404, detail="Service or professional not found")
    if not is_professional_compatible_with_service(svc.category, pro.specialty):
        raise HTTPException(status_code=422, detail="El profesional seleccionado no presta este servicio")

    _ensure_available(db, payload.professional_id, payload.date, payload.time, svc.duration)

    client_name = payload.client_name or current_user.name
    client_email = payload.client_email or current_user.email
    client_phone = payload.client_phone or current_user.phone or ""

    data = {
        "client_name": client_name,
        "client_email": client_email,
        "client_phone": client_phone,
        "service_id": payload.service_id,
        "professional_id": payload.professional_id,
        "date": payload.date,
        "time": payload.time,
        "status": "confirmed",
        "notes": payload.notes or "",
        "history": [],
    }
    try:
        apt = create_appointment(db, data)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slot not available")
    add_history(apt, "Creada por cliente" if current_user.role == "client" else "Creada por admin")
    db.commit()
    db.refresh(apt)

    if settings.smtp_enabled and apt.client_email:
        try:
            send_appointment_confirmation_email(
                to_email=apt.client_email,
                client_name=apt.client_name,
                service_name=svc.name,
                professional_name=pro.name,
                date=apt.date,
                time=apt.time,
                notes=apt.notes,
            )
        except Exception as exc:
            logger.exception(
                'No se pudo enviar correo de confirmacion de cita id=%s email=%s: %s',
                apt.id,
                apt.client_email,
                exc,
            )

    return apt


@router.get("/my", response_model=list[AppointmentOut], dependencies=[Depends(require_roles("client"))])
def my_appointments(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return list_appointments_by_client(db, current_user.email)


@router.get("", response_model=list[AppointmentOut], dependencies=[Depends(require_roles("admin"))])
def list_all(
    date: str | None = None,
    status: str | None = None,
    service_id: int | None = None,
    professional_id: int | None = None,
    db: Session = Depends(get_db),
):
    return list_appointments(
        db,
        date=date,
        status=status,
        service_id=service_id,
        professional_id=professional_id,
    )


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_one(appointment_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    apt = get_appointment(db, appointment_id)
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if current_user.role != "admin" and apt.client_email != current_user.email:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return apt


@router.post("/{appointment_id}/confirm", response_model=AppointmentOut, dependencies=[Depends(require_roles("admin"))])
def confirm(appointment_id: int, payload: AppointmentNotes | None = None, db: Session = Depends(get_db)):
    apt = get_appointment(db, appointment_id)
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    update_data = {"status": "confirmed"}
    if payload and payload.notes is not None:
        update_data["notes"] = payload.notes
    apt = update_appointment(db, apt, update_data)
    add_history(apt, "Confirmada")
    db.commit()
    db.refresh(apt)
    return apt


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel(appointment_id: int, payload: AppointmentNotes | None = None, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    apt = get_appointment(db, appointment_id)
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    if current_user.role != "admin" and apt.client_email != current_user.email:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    update_data = {"status": "cancelled"}
    if payload and payload.notes is not None:
        update_data["notes"] = payload.notes
    apt = update_appointment(db, apt, update_data)
    add_history(apt, "Cancelada")
    db.commit()
    db.refresh(apt)
    return apt


@router.post("/{appointment_id}/attend", response_model=AppointmentOut, dependencies=[Depends(require_roles("admin", "professional"))])
def attend(appointment_id: int, payload: AppointmentNotes | None = None, db: Session = Depends(get_db)):
    apt = get_appointment(db, appointment_id)
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    update_data = {"status": "attended"}
    if payload and payload.notes is not None:
        update_data["notes"] = payload.notes
    apt = update_appointment(db, apt, update_data)
    add_history(apt, "Atendida")
    db.commit()
    db.refresh(apt)
    return apt


@router.post("/{appointment_id}/reschedule", response_model=AppointmentOut, dependencies=[Depends(require_roles("admin"))])
def reschedule(appointment_id: int, payload: AppointmentReschedule, db: Session = Depends(get_db)):
    apt = get_appointment(db, appointment_id)
    if not apt:
        raise HTTPException(status_code=404, detail="Appointment not found")
    svc = get_service(db, apt.service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    _ensure_available(db, apt.professional_id, payload.date, payload.time, svc.duration, appointment_id=apt.id)
    try:
        apt = update_appointment(db, apt, {"date": payload.date, "time": payload.time, "status": "rescheduled"})
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slot not available")
    add_history(apt, f"Reprogramada a {payload.date} {payload.time}")
    db.commit()
    db.refresh(apt)
    return apt
