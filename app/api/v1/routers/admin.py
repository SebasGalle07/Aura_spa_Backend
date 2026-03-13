from datetime import date as dt_date

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.image_storage import save_branding_image
from app.core.security import require_roles
from app.db.deps import get_db
from app.crud.appointment import list_appointments
from app.crud.company import get_or_create_company, update_company, update_branding
from app.services.reservation_workflow import expire_pending_appointments
from app.schemas.company import CompanyData, CompanyUpdate, Branding, BrandingUpdate
from app.schemas.admin import AdminSummary, UploadImageResponse

router = APIRouter()


@router.get("/summary", response_model=AdminSummary, dependencies=[Depends(require_roles("admin"))])
def summary(date: str | None = None, db: Session = Depends(get_db)):
    expire_pending_appointments(db, commit=True)
    target_date = date or dt_date.today().isoformat()
    appointments = list_appointments(db)
    today_apts = [a for a in appointments if a.date == target_date]
    return {
        "date": target_date,
        "today_total": len(today_apts),
        "pending_payment": len([a for a in appointments if a.status == "pending_payment"]),
        "confirmed": len([a for a in appointments if a.status == "confirmed"]),
        "completed": len([a for a in appointments if a.status == "completed"]),
        "expired": len([a for a in appointments if a.status == "expired"]),
        "cancelled": len([a for a in appointments if a.status == "cancelled"]),
        "rescheduled": len([a for a in appointments if a.status == "rescheduled"]),
        "agenda": today_apts,
    }


@router.get("/company", response_model=CompanyData, dependencies=[Depends(require_roles("admin"))])
def get_company(db: Session = Depends(get_db)):
    company = get_or_create_company(db)
    return company


@router.put("/company", response_model=CompanyData, dependencies=[Depends(require_roles("admin"))])
def put_company(payload: CompanyUpdate, db: Session = Depends(get_db)):
    company = get_or_create_company(db)
    return update_company(db, company, payload)


@router.get("/branding", response_model=Branding, dependencies=[Depends(require_roles("admin"))])
def get_branding(db: Session = Depends(get_db)):
    company = get_or_create_company(db)
    return {
        "sp_logo": company.sp_logo,
        "landing_images": {
            "section1": company.landing_section1,
            "section2": company.landing_section2,
            "section3": company.landing_section3,
        },
    }


@router.put("/branding", response_model=Branding, dependencies=[Depends(require_roles("admin"))])
def put_branding(payload: BrandingUpdate, db: Session = Depends(get_db)):
    company = get_or_create_company(db)
    company = update_branding(db, company, payload)
    return {
        "sp_logo": company.sp_logo,
        "landing_images": {
            "section1": company.landing_section1,
            "section2": company.landing_section2,
            "section3": company.landing_section3,
        },
    }


@router.post(
    "/branding/upload",
    response_model=UploadImageResponse,
    dependencies=[Depends(require_roles("admin"))],
)
def upload_branding(file: UploadFile = File(...)):
    return {"url": save_branding_image(file)}
