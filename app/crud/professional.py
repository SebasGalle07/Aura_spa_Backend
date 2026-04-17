from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.text import canonical_text
from app.models.professional import Professional
from app.schemas.professional import ProfessionalCreate, ProfessionalUpdate


def get_professional(db: Session, professional_id: int):
    return db.get(Professional, professional_id)


def get_professional_by_canonical_name(db: Session, name: str):
    return db.scalar(select(Professional).where(Professional.canonical_name == canonical_text(name)))


def list_professionals(db: Session, active: bool | None = None):
    stmt = select(Professional).order_by(Professional.name.asc())
    if active is not None:
        stmt = stmt.where(Professional.active == active)
    return list(db.scalars(stmt).all())


def create_professional(db: Session, professional_in: ProfessionalCreate):
    data = professional_in.model_dump(by_alias=False)
    canonical_name = canonical_text(data["name"])
    existing = db.scalar(select(Professional).where(Professional.canonical_name == canonical_name))
    if existing:
        raise ValueError("Ya existe un profesional con ese nombre")
    obj = Professional(**data, canonical_name=canonical_name)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_professional(db: Session, db_obj: Professional, professional_in: ProfessionalUpdate):
    data = professional_in.model_dump(exclude_unset=True, by_alias=False)
    if "name" in data and data["name"]:
        canonical_name = canonical_text(data["name"])
        existing = db.scalar(
            select(Professional).where(Professional.canonical_name == canonical_name, Professional.id != db_obj.id)
        )
        if existing:
            raise ValueError("Ya existe un profesional con ese nombre")
        data["canonical_name"] = canonical_name
    for field, value in data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_professional(db: Session, db_obj: Professional):
    db.delete(db_obj)
    db.commit()
