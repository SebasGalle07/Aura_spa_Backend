import smtplib
from email.message import EmailMessage

from app.core.config import settings


def send_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    if not settings.smtp_enabled:
        raise RuntimeError('SMTP is not configured')

    msg = EmailMessage()
    from_name = settings.SMTP_FROM_NAME.strip()
    if from_name:
        msg['From'] = f'{from_name} <{settings.SMTP_FROM_EMAIL}>'
    else:
        msg['From'] = settings.SMTP_FROM_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.set_content(text_body)

    if html_body:
        msg.add_alternative(html_body, subtype='html')

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(msg)


def send_password_reset_email(to_email: str, reset_link: str) -> None:
    subject = 'Aura Spa - Recuperacion de contrasena'
    text = (
        'Recibimos una solicitud para restablecer tu contrasena.\n\n'
        f'Ingresa a este enlace para continuar:\n{reset_link}\n\n'
        f'Este enlace expira en {settings.RESET_TOKEN_EXPIRE_MINUTES} minutos.\n'
        'Si no realizaste esta solicitud, ignora este mensaje.'
    )
    html = f"""
    <p>Recibimos una solicitud para restablecer tu contrasena.</p>
    <p><a href=\"{reset_link}\">Restablecer contrasena</a></p>
    <p>Este enlace expira en {settings.RESET_TOKEN_EXPIRE_MINUTES} minutos.</p>
    <p>Si no realizaste esta solicitud, ignora este mensaje.</p>
    """
    send_email(to_email, subject, text, html)


def send_contact_notification(to_email: str, sender_name: str, sender_email: str, message: str) -> None:
    subject = 'Aura Spa - Nuevo mensaje de contacto'
    text = (
        'Se recibio un nuevo mensaje desde el formulario de contacto.\n\n'
        f'Nombre: {sender_name}\n'
        f'Correo: {sender_email}\n\n'
        'Mensaje:\n'
        f'{message}\n'
    )
    html = f"""
    <p>Se recibio un nuevo mensaje desde el formulario de contacto.</p>
    <p><strong>Nombre:</strong> {sender_name}</p>
    <p><strong>Correo:</strong> {sender_email}</p>
    <p><strong>Mensaje:</strong></p>
    <p>{message.replace('\n', '<br/>')}</p>
    """
    send_email(to_email, subject, text, html)


def send_appointment_confirmation_email(
    to_email: str,
    client_name: str,
    service_name: str,
    professional_name: str,
    date: str,
    time: str,
    notes: str | None = None,
) -> None:
    subject = 'Aura Spa - Confirmacion de cita'
    notes_text = notes.strip() if notes else ''
    text = (
        f'Hola {client_name},\n\n'
        'Tu cita fue confirmada con exito.\n\n'
        f'Servicio: {service_name}\n'
        f'Profesional: {professional_name}\n'
        f'Fecha: {date}\n'
        f'Hora: {time}\n'
    )
    if notes_text:
        text += f'Observaciones: {notes_text}\n'
    text += '\nTe esperamos en Aura Spa.'

    html = f"""
    <p>Hola {client_name},</p>
    <p>Tu cita fue confirmada con exito.</p>
    <ul>
      <li><strong>Servicio:</strong> {service_name}</li>
      <li><strong>Profesional:</strong> {professional_name}</li>
      <li><strong>Fecha:</strong> {date}</li>
      <li><strong>Hora:</strong> {time}</li>
    </ul>
    """
    if notes_text:
        html += f"<p><strong>Observaciones:</strong> {notes_text}</p>"
    html += '<p>Te esperamos en Aura Spa.</p>'
    send_email(to_email, subject, text, html)
