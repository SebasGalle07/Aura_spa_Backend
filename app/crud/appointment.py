from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment


def list_appointments(db: Session):
    return list(db.scalars(select(Appointment)).all())


def list_appointments_by_client(db: Session, email: str):
    return list(db.scalars(select(Appointment).where(Appointment.client_email == email)).all())


def list_appointments_by_professional_and_date(db: Session, professional_id: int, date: str):
    stmt = select(Appointment).where(
        Appointment.professional_id == professional_id,
        Appointment.date == date,
    )
    return list(db.scalars(stmt).all())


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
