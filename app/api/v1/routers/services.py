from pathlib import Path
import shutil
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import require_roles
from app.db.deps import get_db
from app.crud.service import list_services, get_service, create_service, update_service, delete_service
from app.schemas.service import ServiceOut, ServiceCreate, ServiceUpdate

router = APIRouter()

_SERVICES_MEDIA_DIR = Path(settings.MEDIA_ROOT) / "services"


def _guess_ext(filename: str | None, content_type: str | None) -> str:
    if filename:
        ext = Path(filename).suffix.lower()
        if ext:
            return ext
    if content_type:
        mapping = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
        }
        return mapping.get(content_type.lower(), "")
    return ""


def _delete_image_if_exists(image_url: str | None) -> None:
    if not image_url:
        return
    prefix = f"{settings.MEDIA_URL}/"
    if image_url.startswith(prefix):
        rel_path = image_url[len(prefix) :]
        path = Path(settings.MEDIA_ROOT) / rel_path
        if path.exists() and path.is_file():
            path.unlink()


@router.get("", response_model=list[ServiceOut])
def list_all(active: bool | None = None, db: Session = Depends(get_db)):
    return list_services(db, active=active)


@router.get("/{service_id}", response_model=ServiceOut)
def get_one(service_id: int, db: Session = Depends(get_db)):
    svc = get_service(db, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    return svc


@router.post("", response_model=ServiceOut, dependencies=[Depends(require_roles("admin"))])
def create_one(service_in: ServiceCreate, db: Session = Depends(get_db)):
    return create_service(db, service_in)


@router.put("/{service_id}", response_model=ServiceOut, dependencies=[Depends(require_roles("admin"))])
def update_one(service_id: int, service_in: ServiceUpdate, db: Session = Depends(get_db)):
    svc = get_service(db, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    return update_service(db, svc, service_in)


@router.delete("/{service_id}", dependencies=[Depends(require_roles("admin"))])
def delete_one(service_id: int, soft: bool = True, db: Session = Depends(get_db)):
    svc = get_service(db, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    if soft:
        svc.active = False
        db.add(svc)
        db.commit()
        return {"ok": True, "soft": True}
    delete_service(db, svc)
    return {"ok": True, "soft": False}


@router.post("/{service_id}/image", response_model=ServiceOut, dependencies=[Depends(require_roles("admin"))])
def upload_image(service_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    svc = get_service(db, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    _SERVICES_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    ext = _guess_ext(file.filename, file.content_type)
    filename = f"service_{service_id}_{uuid4().hex}{ext}"
    dest = _SERVICES_MEDIA_DIR / filename

    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    _delete_image_if_exists(svc.image)
    svc.image = f"{settings.MEDIA_URL}/services/{filename}"
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc


@router.delete("/{service_id}/image", response_model=ServiceOut, dependencies=[Depends(require_roles("admin"))])
def delete_image(service_id: int, db: Session = Depends(get_db)):
    svc = get_service(db, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")
    _delete_image_if_exists(svc.image)
    svc.image = None
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc
