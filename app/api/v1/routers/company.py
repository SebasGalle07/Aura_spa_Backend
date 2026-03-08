import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.mailer import send_contact_notification
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
def send_contact(payload: ContactMessageIn, db: Session = Depends(get_db)):
    if not settings.smtp_enabled:
        logger.warning('Formulario de contacto rechazado: SMTP no configurado')
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Canal de contacto no disponible temporalmente. Usa WhatsApp mientras lo activamos.',
        )

    company = get_or_create_company(db)
    recipient = (company.email or settings.SMTP_FROM_EMAIL or '').strip()
    if not recipient:
        logger.error('Formulario de contacto rechazado: no hay correo de destino configurado')
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='No hay correo de atencion configurado.',
        )

    try:
        send_contact_notification(
            to_email=recipient,
            sender_name=payload.name.strip(),
            sender_email=str(payload.email).strip(),
            message=payload.message.strip(),
        )
    except Exception as exc:
        logger.exception('Error enviando formulario de contacto a %s: %s', recipient, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='No fue posible enviar el mensaje en este momento.',
        ) from exc

    logger.info(
        'Mensaje de contacto enviado. from=%s to=%s',
        payload.email,
        recipient,
    )
    return {'ok': True}
