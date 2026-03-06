import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    return bool(settings.SMTP_ENABLED and settings.SMTP_HOST and settings.SMTP_FROM_EMAIL)


def send_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> bool:
    if not _smtp_configured():
        logger.warning("SMTP no configurado. No se envia correo. subject=%s to=%s", subject, to_email)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to_email
    msg.set_content(text_body)
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception:
        logger.exception("Fallo enviando correo SMTP. to=%s", to_email)
        return False


def send_password_reset_email(to_email: str, user_name: str, reset_link: str) -> bool:
    subject = "Aura Spa - Recuperacion de contrasena"
    text = (
        f"Hola {user_name},\n\n"
        "Recibimos una solicitud para restablecer tu contrasena.\n"
        f"Abre este enlace: {reset_link}\n\n"
        "Si no solicitaste este cambio, ignora este mensaje."
    )
    html = (
        f"<p>Hola <strong>{user_name}</strong>,</p>"
        "<p>Recibimos una solicitud para restablecer tu contrasena.</p>"
        f"<p><a href=\"{reset_link}\">Restablecer contrasena</a></p>"
        "<p>Si no solicitaste este cambio, ignora este mensaje.</p>"
    )
    return send_email(to_email, subject, text, html)


def send_contact_email(sender_name: str, sender_email: str, message: str) -> bool:
    subject = "Aura Spa - Nuevo mensaje de contacto"
    text = (
        "Nuevo mensaje de contacto:\n\n"
        f"Nombre: {sender_name}\n"
        f"Correo: {sender_email}\n\n"
        f"Mensaje:\n{message}\n"
    )
    html = (
        "<h3>Nuevo mensaje de contacto</h3>"
        f"<p><strong>Nombre:</strong> {sender_name}</p>"
        f"<p><strong>Correo:</strong> {sender_email}</p>"
        f"<p><strong>Mensaje:</strong><br>{message}</p>"
    )
    return send_email(settings.CONTACT_TO_EMAIL, subject, text, html)
