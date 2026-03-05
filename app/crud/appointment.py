from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
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
    return list(db.scalars(stmt).all())


def list_appointments_by_client(db: Session, email: str):
    return list(db.scalars(select(Appointment).where(Appointment.client_email == email)).all())


def list_appointments_by_professional_and_date(db: Session, professional_id: int, date: str):
    stmt = select(Appointment).where(
        Appointment.professional_id == professional_id,
        Appointment.date == date,
    )
    return list(db.scalars(stmt).all())


def list_appointments_by_professional_and_date_with_duration(db: Session, professional_id: int, date: str):
    stmt = (
        select(Appointment, Service.duration)
        .join(Service, Appointment.service_id == Service.id)
        .where(
            Appointment.professional_id == professional_id,
            Appointment.date == date,
        )
    )
    return list(db.execute(stmt).all())


def get_appointment(db: Session, appointment_id: int):
    return db.get(Appointment, appointment_id)


def create_appointment(db: Session, data: dict):
    obj = Appointment(**data)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_appointment(db: Session, db_obj: Appointment, data: dict):
    for field, value in data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def add_history(db_obj: Appointment, action: str):
    history = db_obj.history or []
    history.append({"action": action, "at": datetime.now().isoformat(timespec="minutes")})
    db_obj.history = history
