from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.mailer import send_contact_email
from app.db.deps import get_db
from app.crud.company import get_or_create_company
from app.schemas.company import CompanyData, Branding
from app.schemas.contact import ContactMessageIn, ContactMessageOut

router = APIRouter()


@router.get("/company", response_model=CompanyData)
def public_company(db: Session = Depends(get_db)):
    return get_or_create_company(db)


@router.get("/branding", response_model=Branding)
def public_branding(db: Session = Depends(get_db)):
    company = get_or_create_company(db)
    return {
        "sp_logo": company.sp_logo,
        "landing_images": {
            "section1": company.landing_section1,
            "section2": company.landing_section2,
            "section3": company.landing_section3,
        },
    }


@router.post("/contact", response_model=ContactMessageOut)
def send_contact(payload: ContactMessageIn):
    if not settings.SMTP_ENABLED:
        raise HTTPException(status_code=503, detail="Servicio de correo no configurado")

    sent = send_contact_email(
        sender_name=payload.name.strip(),
        sender_email=payload.email,
        message=payload.message.strip(),
    )
    if not sent:
        raise HTTPException(status_code=502, detail="No fue posible enviar el mensaje")
    return {"ok": True}
