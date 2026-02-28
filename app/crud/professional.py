from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.professional import Professional
from app.schemas.professional import ProfessionalCreate, ProfessionalUpdate


def get_professional(db: Session, professional_id: int):
    return db.get(Professional, professional_id)


def list_professionals(db: Session, active: bool | None = None):
    stmt = select(Professional)
    if active is not None:
        stmt = stmt.where(Professional.active == active)
    return list(db.scalars(stmt).all())


def create_professional(db: Session, professional_in: ProfessionalCreate):
    obj = Professional(**professional_in.model_dump(by_alias=False))
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_professional(db: Session, db_obj: Professional, professional_in: ProfessionalUpdate):
    data = professional_in.model_dump(exclude_unset=True, by_alias=False)
    for field, value in data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_professional(db: Session, db_obj: Professional):
    db.delete(db_obj)
    db.commit()
