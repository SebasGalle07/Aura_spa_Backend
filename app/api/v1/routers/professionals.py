from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_roles
from app.core.specialty_match import is_professional_compatible_with_service
from app.db.deps import get_db
from app.crud.service import get_service
from app.crud.professional import list_professionals, get_professional, create_professional, update_professional
from app.schemas.professional import ProfessionalOut, ProfessionalCreate, ProfessionalUpdate

router = APIRouter()


@router.get("", response_model=list[ProfessionalOut])
def list_all(active: bool | None = None, service_id: int | None = None, db: Session = Depends(get_db)):
    professionals = list_professionals(db, active=active)
    if service_id is None:
        return professionals

    svc = get_service(db, service_id)
    if not svc:
        raise HTTPException(status_code=404, detail="Service not found")

    return [
        pro for pro in professionals if is_professional_compatible_with_service(svc.category, pro.specialty)
    ]


@router.get("/{professional_id}", response_model=ProfessionalOut)
def get_one(professional_id: int, db: Session = Depends(get_db)):
    pro = get_professional(db, professional_id)
    if not pro:
        raise HTTPException(status_code=404, detail="Professional not found")
    return pro


@router.post("", response_model=ProfessionalOut, dependencies=[Depends(require_roles("admin"))])
def create_one(professional_in: ProfessionalCreate, db: Session = Depends(get_db)):
    return create_professional(db, professional_in)


@router.put("/{professional_id}", response_model=ProfessionalOut, dependencies=[Depends(require_roles("admin"))])
def update_one(professional_id: int, professional_in: ProfessionalUpdate, db: Session = Depends(get_db)):
    pro = get_professional(db, professional_id)
    if not pro:
        raise HTTPException(status_code=404, detail="Professional not found")
    return update_professional(db, pro, professional_in)
