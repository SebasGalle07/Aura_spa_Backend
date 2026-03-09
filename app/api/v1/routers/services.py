from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.image_storage import delete_public_image_by_url, save_public_image
from app.core.security import require_roles
from app.crud.service import create_service, delete_service, get_service, list_services, update_service
from app.db.deps import get_db
from app.schemas.service import ServiceCreate, ServiceOut, ServiceUpdate

router = APIRouter()


@router.get('', response_model=list[ServiceOut])
def list_all(active: bool | None = None, db: Session = Depends(get_db)):
    return list_services(db, active=active)


@router.get('/{service_id}', response_model=ServiceOut)
def get_one(service_id: int, db: Session = Depends(get_db)):
    svc = get_service(db, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail='Service not found')
    return svc


@router.post('', response_model=ServiceOut, dependencies=[Depends(require_roles('admin'))])
def create_one(service_in: ServiceCreate, db: Session = Depends(get_db)):
    return create_service(db, service_in)


@router.put('/{service_id}', response_model=ServiceOut, dependencies=[Depends(require_roles('admin'))])
def update_one(service_id: int, service_in: ServiceUpdate, db: Session = Depends(get_db)):
    svc = get_service(db, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail='Service not found')
    return update_service(db, svc, service_in)


@router.delete('/{service_id}', dependencies=[Depends(require_roles('admin'))])
def delete_one(service_id: int, soft: bool = True, db: Session = Depends(get_db)):
    svc = get_service(db, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail='Service not found')
    if soft:
        svc.active = False
        db.add(svc)
        db.commit()
        return {'ok': True, 'soft': True}
    delete_public_image_by_url(svc.image)
    delete_service(db, svc)
    return {'ok': True, 'soft': False}


@router.post('/{service_id}/image', response_model=ServiceOut, dependencies=[Depends(require_roles('admin'))])
def upload_image(service_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    svc = get_service(db, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail='Service not found')

    image_url = save_public_image(file, folder='services', stem=f'service_{service_id}')
    delete_public_image_by_url(svc.image)

    svc.image = image_url
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc


@router.delete('/{service_id}/image', response_model=ServiceOut, dependencies=[Depends(require_roles('admin'))])
def delete_image(service_id: int, db: Session = Depends(get_db)):
    svc = get_service(db, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail='Service not found')
    delete_public_image_by_url(svc.image)
    svc.image = None
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc
