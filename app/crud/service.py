from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.text import canonical_text
from app.models.service import Service
from app.schemas.service import ServiceCreate, ServiceUpdate


def get_service(db: Session, service_id: int):
    return db.get(Service, service_id)


def get_service_by_canonical_name(db: Session, name: str):
    return db.scalar(select(Service).where(Service.canonical_name == canonical_text(name)))


def list_services(db: Session, active: bool | None = None):
    stmt = select(Service).order_by(Service.name.asc())
    if active is not None:
        stmt = stmt.where(Service.active == active)
    return list(db.scalars(stmt).all())


def create_service(db: Session, service_in: ServiceCreate):
    data = service_in.model_dump(by_alias=False)
    canonical_name = canonical_text(data["name"])
    existing = db.scalar(select(Service).where(Service.canonical_name == canonical_name))
    if existing:
        raise ValueError("Ya existe un servicio con ese nombre")
    obj = Service(**data, canonical_name=canonical_name)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_service(db: Session, db_obj: Service, service_in: ServiceUpdate):
    data = service_in.model_dump(exclude_unset=True, by_alias=False)
    if "name" in data and data["name"]:
        canonical_name = canonical_text(data["name"])
        existing = db.scalar(select(Service).where(Service.canonical_name == canonical_name, Service.id != db_obj.id))
        if existing:
            raise ValueError("Ya existe un servicio con ese nombre")
        data["canonical_name"] = canonical_name
    for field, value in data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_service(db: Session, db_obj: Service):
    db.delete(db_obj)
    db.commit()
