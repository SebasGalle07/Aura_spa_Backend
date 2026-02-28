from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.service import Service
from app.schemas.service import ServiceCreate, ServiceUpdate


def get_service(db: Session, service_id: int):
    return db.get(Service, service_id)


def list_services(db: Session, active: bool | None = None):
    stmt = select(Service)
    if active is not None:
        stmt = stmt.where(Service.active == active)
    return list(db.scalars(stmt).all())


def create_service(db: Session, service_in: ServiceCreate):
    obj = Service(**service_in.model_dump(by_alias=False))
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update_service(db: Session, db_obj: Service, service_in: ServiceUpdate):
    data = service_in.model_dump(exclude_unset=True, by_alias=False)
    for field, value in data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def delete_service(db: Session, db_obj: Service):
    db.delete(db_obj)
    db.commit()
