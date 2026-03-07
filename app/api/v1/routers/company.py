import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.crud.company import get_or_create_company
from app.db.deps import get_db
from app.schemas.company import Branding, CompanyData
from app.schemas.contact import ContactMessageIn, ContactMessageOut

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get('/company', response_model=CompanyData)
def public_company(db: Session = Depends(get_db)):
    return get_or_create_company(db)


@router.get('/branding', response_model=Branding)
def public_branding(db: Session = Depends(get_db)):
    company = get_or_create_company(db)
    return {
        'sp_logo': company.sp_logo,
        'landing_images': {
            'section1': company.landing_section1,
            'section2': company.landing_section2,
            'section3': company.landing_section3,
        },
    }


@router.post('/contact', response_model=ContactMessageOut)
def send_contact(payload: ContactMessageIn):
    logger.info('Mensaje de contacto recibido. name=%s email=%s', payload.name, payload.email)
    return {'ok': True}
