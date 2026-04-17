import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.mailer import send_account_cancellation_confirmation_email
from app.core.security import get_current_user, require_roles
from app.core.time import utc_now
from app.crud.audit import (
    create_account_cancellation_request,
    create_audit_log,
    get_account_cancellation_request,
    get_open_account_cancellation_request,
    list_account_cancellation_requests,
)
from app.crud.token import revoke_user_refresh_tokens
from app.crud.user import get_user_by_id
from app.db.deps import get_db
from app.schemas.audit import (
    AccountCancellationRequestCreate,
    AccountCancellationRequestOut,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/me", response_model=AccountCancellationRequestOut)
def request_account_cancellation(
    payload: AccountCancellationRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Cancela la inscripcion del cliente de forma inmediata.

    La cuenta queda desactivada al instante, los tokens son revocados
    y se envia un correo de confirmacion al usuario.
    """
    reason = payload.reason.strip()
    if len(reason) < 10:
        raise HTTPException(status_code=422, detail="Indica un motivo de al menos 10 caracteres")

    existing = get_open_account_cancellation_request(db, current_user.id)
    if existing:
        raise HTTPException(status_code=409, detail="Tu cuenta ya fue cancelada o tienes una solicitud en proceso")

    # Crear registro con status aprobado directamente (cancelacion inmediata)
    now = utc_now()
    cancellation = create_account_cancellation_request(
        db,
        user_id=current_user.id,
        reason=reason,
        status="approved",
        reviewed_at=now,
    )

    # Desactivar la cuenta del usuario
    user = get_user_by_id(db, current_user.id)
    if user:
        user.is_active = False
        user.deactivated_at = now
        db.add(user)
        db.commit()
        db.refresh(user)

    # Revocar todos los refresh tokens activos
    revoke_user_refresh_tokens(db, current_user.id)

    # Enviar correo de confirmacion de cancelacion
    if settings.smtp_enabled:
        try:
            send_account_cancellation_confirmation_email(
                to_email=current_user.email,
                account_name=current_user.name,
            )
        except Exception as exc:
            logger.exception(
                "No se pudo enviar correo de confirmacion de cancelacion a user_id=%s: %s",
                current_user.id,
                exc,
            )

    create_audit_log(
        db,
        action="account_cancellation_immediate",
        entity_type="account_cancellation_request",
        entity_id=cancellation.id,
        actor=current_user,
        new_value={"status": "approved", "reason": reason, "immediate": True},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return cancellation


@router.get("", response_model=list[AccountCancellationRequestOut], dependencies=[Depends(require_roles("admin"))])
def list_cancellation_requests(db: Session = Depends(get_db)):
    """Lista el historial de cancelaciones de inscripcion (solo lectura para admin)."""
    return list_account_cancellation_requests(db)


@router.get("/{request_id}", response_model=AccountCancellationRequestOut, dependencies=[Depends(require_roles("admin"))])
def get_cancellation_request(request_id: int, db: Session = Depends(get_db)):
    """Detalle de una solicitud de cancelacion (solo lectura)."""
    cancellation = get_account_cancellation_request(db, request_id)
    if not cancellation:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return cancellation
