import html
import smtplib
from email.message import EmailMessage
from datetime import datetime

from app.core.config import settings
from app.core.time import utc_now


BRAND = {
    "bg": "#faf7f2",
    "surface": "#ffffff",
    "surface_alt": "#f6efe7",
    "border": "#e8ddd0",
    "text": "#3d2b24",
    "muted": "#78665a",
    "accent": "#c9a96e",
    "accent_dark": "#8b6f5e",
    "success_bg": "#eef4ea",
    "success_text": "#486044",
}


def send_email(to_email: str, subject: str, text_body: str, html_body: str | None = None) -> None:
    if not settings.smtp_enabled:
        raise RuntimeError("SMTP is not configured")

    msg = EmailMessage()
    from_name = settings.SMTP_FROM_NAME.strip()
    if from_name:
        msg["From"] = f"{from_name} <{settings.SMTP_FROM_EMAIL}>"
    else:
        msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(text_body)

    if html_body:
        msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(msg)


def _escape(value: str | None) -> str:
    return html.escape((value or "").strip())


def _paragraphs(lines: list[str]) -> str:
    return "".join(
        f'<p style="margin:0 0 14px; font-size:15px; line-height:1.7; color:{BRAND["muted"]};">{_escape(line)}</p>'
        for line in lines
        if line.strip()
    )


def _cta_button(label: str, url: str) -> str:
    safe_label = _escape(label)
    safe_url = html.escape(url, quote=True)
    return (
        f'<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin: 28px 0 12px;">'
        "<tr>"
        f'<td style="border-radius:999px; background:{BRAND["text"]};">'
        f'<a href="{safe_url}" '
        'style="display:inline-block; padding:14px 24px; font-size:14px; font-weight:700; '
        f'color:{BRAND["bg"]}; text-decoration:none;">{safe_label}</a>'
        "</td>"
        "</tr>"
        "</table>"
    )


def _details_table(details: list[tuple[str, str]]) -> str:
    rows: list[str] = []
    for label, value in details:
        clean_value = value.strip()
        if not clean_value:
            continue
        rows.append(
            "<tr>"
            f'<td style="padding:12px 0; border-bottom:1px solid {BRAND["border"]}; '
            f'font-size:13px; color:{BRAND["muted"]}; width:38%;">{_escape(label)}</td>'
            f'<td style="padding:12px 0; border-bottom:1px solid {BRAND["border"]}; '
            f'font-size:14px; color:{BRAND["text"]}; font-weight:600;">{_escape(clean_value)}</td>'
            "</tr>"
        )
    if not rows:
        return ""
    return (
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
        f'style="margin:20px 0 0; background:{BRAND["surface_alt"]}; border:1px solid {BRAND["border"]}; '
        'border-radius:16px; padding:0 18px;">'
        + "".join(rows)
        + "</table>"
    )


def _message_card(title: str, body_html: str, badge: str | None = None, tone: str = "default") -> str:
    badge_html = ""
    if badge:
        badge_html = (
            f'<div style="display:inline-block; margin:0 0 14px; padding:8px 12px; border-radius:999px; '
            f'background:{BRAND["success_bg"] if tone == "success" else BRAND["surface_alt"]}; '
            f'color:{BRAND["success_text"] if tone == "success" else BRAND["accent_dark"]}; '
            'font-size:12px; font-weight:700; letter-spacing:0.02em;">'
            f"{_escape(badge)}</div>"
        )
    return (
        f'<div style="background:{BRAND["surface"]}; border:1px solid {BRAND["border"]}; border-radius:24px; '
        'padding:32px 28px; box-shadow:0 18px 40px rgba(61, 43, 36, 0.08);">'
        f"{badge_html}"
        f'<h1 style="margin:0 0 14px; font-size:32px; line-height:1.1; font-weight:700; color:{BRAND["text"]};">'
        f"{_escape(title)}</h1>"
        f"{body_html}"
        "</div>"
    )


def _build_email_layout(
    *,
    preheader: str,
    eyebrow: str,
    title: str,
    intro_lines: list[str],
    details: list[tuple[str, str]] | None = None,
    cta_label: str | None = None,
    cta_url: str | None = None,
    footer_lines: list[str] | None = None,
    badge: str | None = None,
    tone: str = "default",
    closing_note: str | None = None,
) -> str:
    intro_html = _paragraphs(intro_lines)
    details_html = _details_table(details or [])
    cta_html = _cta_button(cta_label, cta_url) if cta_label and cta_url else ""
    closing_html = (
        f'<p style="margin:18px 0 0; font-size:14px; line-height:1.7; color:{BRAND["muted"]};">{_escape(closing_note)}</p>'
        if closing_note
        else ""
    )
    footer_html = _paragraphs(footer_lines or [])

    content = (
        f'<div style="display:none; max-height:0; overflow:hidden; opacity:0; color:transparent;">{_escape(preheader)}</div>'
        f'<div style="max-width:640px; margin:0 auto; padding:32px 20px 40px;">'
        f'<div style="margin:0 0 18px; padding:0 6px;">'
        f'<div style="font-size:12px; font-weight:700; letter-spacing:0.14em; text-transform:uppercase; color:{BRAND["accent_dark"]};">'
        f"{_escape(eyebrow)}</div>"
        f'<div style="margin-top:10px; width:72px; height:4px; border-radius:999px; background:linear-gradient(90deg, {BRAND["accent"]}, {BRAND["accent_dark"]});"></div>'
        "</div>"
        f'{_message_card(title, intro_html + details_html + cta_html + closing_html, badge=badge, tone=tone)}'
        f'<div style="padding:18px 6px 0;">{footer_html}'
        f'<p style="margin:14px 0 0; font-size:12px; line-height:1.6; color:{BRAND["muted"]};">'
        f"Este es un correo automatico enviado por {_escape(settings.SMTP_FROM_NAME or 'Aura Spa')}."
        "</p>"
        "</div>"
        "</div>"
    )

    return (
        "<!doctype html>"
        '<html lang="es">'
        "<head>"
        '<meta charset="utf-8" />'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />'
        f"<title>{_escape(title)}</title>"
        "</head>"
        f'<body style="margin:0; padding:0; background:{BRAND["bg"]}; color:{BRAND["text"]}; font-family:Arial, Helvetica, sans-serif;">'
        f"{content}"
        "</body>"
        "</html>"
    )


def send_email_verification_email(to_email: str, verification_link: str) -> None:
    subject = "Aura Spa - Verifica tu correo"
    text = (
        "Gracias por crear tu cuenta en Aura Spa.\n\n"
        f"Para activar tu cuenta, ingresa a este enlace:\n{verification_link}\n\n"
        f"Este enlace expira en {settings.VERIFY_EMAIL_TOKEN_EXPIRE_HOURS} horas.\n"
        "Si no creaste esta cuenta, ignora este mensaje."
    )
    html_body = _build_email_layout(
        preheader="Activa tu cuenta para empezar a reservar en Aura Spa.",
        eyebrow="Verificacion de cuenta",
        title="Activa tu cuenta",
        intro_lines=[
            "Gracias por crear tu cuenta en Aura Spa.",
            "Para proteger tu acceso, necesitamos confirmar que este correo te pertenece.",
        ],
        cta_label="Verificar correo",
        cta_url=verification_link,
        footer_lines=[
            f"Este enlace expira en {settings.VERIFY_EMAIL_TOKEN_EXPIRE_HOURS} horas.",
            "Si no creaste esta cuenta, puedes ignorar este mensaje sin hacer nada.",
        ],
        badge="Accion requerida",
    )
    send_email(to_email, subject, text, html_body)


def send_password_reset_email(to_email: str, reset_link: str) -> None:
    subject = "Aura Spa - Recuperacion de contrasena"
    text = (
        "Recibimos una solicitud para restablecer tu contrasena.\n\n"
        f"Ingresa a este enlace para continuar:\n{reset_link}\n\n"
        f"Este enlace expira en {settings.RESET_TOKEN_EXPIRE_MINUTES} minutos.\n"
        "Si no realizaste esta solicitud, ignora este mensaje."
    )
    html_body = _build_email_layout(
        preheader="Usa este enlace para restablecer tu contrasena de Aura Spa.",
        eyebrow="Seguridad de acceso",
        title="Restablece tu contrasena",
        intro_lines=[
            "Recibimos una solicitud para cambiar la contrasena de tu cuenta.",
            "Si fuiste tu, continua desde el siguiente enlace seguro.",
        ],
        cta_label="Restablecer contrasena",
        cta_url=reset_link,
        footer_lines=[
            f"Este enlace expira en {settings.RESET_TOKEN_EXPIRE_MINUTES} minutos.",
            "Si no solicitaste este cambio, te recomendamos ignorar este correo.",
        ],
        badge="Solicitud de seguridad",
    )
    send_email(to_email, subject, text, html_body)


def send_contact_notification(to_email: str, sender_name: str, sender_email: str, message: str) -> None:
    subject = "Aura Spa - Nuevo mensaje de contacto"
    clean_message = (message or "").strip()
    text = (
        "Se recibio un nuevo mensaje desde el formulario de contacto.\n\n"
        f"Nombre: {sender_name}\n"
        f"Correo: {sender_email}\n\n"
        "Mensaje:\n"
        f"{clean_message}\n"
    )
    html_body = _build_email_layout(
        preheader="Tienes un nuevo mensaje desde el formulario de contacto.",
        eyebrow="Buzon de contacto",
        title="Nuevo mensaje recibido",
        intro_lines=[
            "Se registro una nueva solicitud desde el sitio web de Aura Spa.",
        ],
        details=[
            ("Nombre", sender_name),
            ("Correo", sender_email),
            ("Mensaje", clean_message),
        ],
        footer_lines=[
            "Responde directamente al cliente desde tu canal de atencion habitual.",
        ],
        badge="Notificacion interna",
    )
    send_email(to_email, subject, text, html_body)


def send_appointment_confirmation_email(
    to_email: str,
    client_name: str,
    service_name: str,
    professional_name: str,
    date: str,
    time: str,
    notes: str | None = None,
) -> None:
    subject = "Aura Spa - Confirmacion de cita"
    notes_text = (notes or "").strip()
    text = (
        f"Hola {client_name},\n\n"
        "Tu cita fue confirmada con exito.\n\n"
        f"Servicio: {service_name}\n"
        f"Profesional: {professional_name}\n"
        f"Fecha: {date}\n"
        f"Hora: {time}\n"
    )
    if notes_text:
        text += f"Observaciones: {notes_text}\n"
    text += "\nTe esperamos en Aura Spa."

    details = [
        ("Cliente", client_name),
        ("Servicio", service_name),
        ("Profesional", professional_name),
        ("Fecha", date),
        ("Hora", time),
    ]
    if notes_text:
        details.append(("Observaciones", notes_text))

    html_body = _build_email_layout(
        preheader="Tu reserva ya fue confirmada en Aura Spa.",
        eyebrow="Reserva confirmada",
        title="Tu cita ya esta asegurada",
        intro_lines=[
            f"Hola {client_name}, tu anticipo fue validado y la reserva quedo confirmada.",
            "Aqui tienes el resumen para que lo conserves a mano.",
        ],
        details=details,
        footer_lines=[
            "Si necesitas reprogramar tu cita, recuerda hacerlo con la anticipacion permitida por el sistema.",
            "Te esperamos en Aura Spa para brindarte una experiencia de bienestar cuidada al detalle.",
        ],
        badge="Confirmada",
        tone="success",
    )
    send_email(to_email, subject, text, html_body)


def send_settlement_receipt_email(
    to_email: str,
    client_name: str,
    receipt_number: str,
    service_name: str,
    professional_name: str,
    appointment_date: str,
    appointment_time: str,
    total_amount: str,
    deposit_amount: str,
    paid_amount: str,
    balance_amount: str,
    issued_at: datetime,
) -> None:
    subject = f"Aura Spa - Comprobante interno {receipt_number}"
    issued_label = issued_at.strftime("%Y-%m-%d %H:%M")
    text = (
        f"Hola {client_name},\n\n"
        "Tu servicio fue liquidado y se genero el comprobante interno de pago.\n\n"
        f"Comprobante: {receipt_number}\n"
        f"Servicio: {service_name}\n"
        f"Profesional: {professional_name}\n"
        f"Fecha de cita: {appointment_date} {appointment_time}\n"
        f"Total: {total_amount}\n"
        f"Anticipo: {deposit_amount}\n"
        f"Total pagado: {paid_amount}\n"
        f"Saldo pendiente: {balance_amount}\n"
        f"Fecha de emision: {issued_label}\n\n"
        "Este comprobante es interno y no reemplaza una factura electronica legal."
    )
    html_body = _build_email_layout(
        preheader=f"Comprobante interno {receipt_number} emitido por Aura Spa.",
        eyebrow="Comprobante interno",
        title="Tu comprobante de servicio",
        intro_lines=[
            f"Hola {client_name}, tu servicio fue liquidado correctamente.",
            "Adjuntamos el resumen interno del pago registrado en Aura Spa.",
        ],
        details=[
            ("Comprobante", receipt_number),
            ("Servicio", service_name),
            ("Profesional", professional_name),
            ("Fecha de cita", f"{appointment_date} {appointment_time}"),
            ("Total del servicio", total_amount),
            ("Anticipo pagado", deposit_amount),
            ("Total pagado", paid_amount),
            ("Saldo pendiente", balance_amount),
            ("Fecha de emision", issued_label),
        ],
        footer_lines=[
            "Este documento es un comprobante interno de servicio.",
            "No corresponde a factura electronica DIAN ni reemplaza obligaciones tributarias legales.",
        ],
        badge="Liquidado",
        tone="success",
    )
    send_email(to_email, subject, text, html_body)


def send_email_change_alert_email(
    to_email: str,
    account_name: str,
    previous_email: str,
    new_email: str,
    requested_at: datetime | None = None,
) -> None:
    event_time = (requested_at or utc_now()).strftime("%Y-%m-%d %H:%M UTC")
    subject = "Aura Spa - Aviso de cambio de correo"
    text = (
        f"Hola {account_name},\n\n"
        "Recibimos una solicitud para cambiar el correo asociado a tu cuenta de Aura Spa.\n\n"
        f"Correo anterior: {previous_email}\n"
        f"Correo nuevo solicitado: {new_email}\n"
        f"Fecha y hora de la solicitud: {event_time}\n\n"
        "Si reconoces este cambio, no necesitas hacer nada en este correo.\n"
        "Si no autorizaste esta solicitud, te recomendamos contactarnos de inmediato."
    )
    html_body = _build_email_layout(
        preheader="Detectamos una solicitud de cambio de correo en tu cuenta de Aura Spa.",
        eyebrow="Alerta de seguridad",
        title="Solicitud de cambio de correo",
        intro_lines=[
            f"Hola {account_name}, registramos una solicitud para cambiar el correo de tu cuenta.",
            "Este mensaje se envia al correo anterior para que puedas detectar cambios no autorizados.",
        ],
        details=[
            ("Correo anterior", previous_email),
            ("Correo nuevo solicitado", new_email),
            ("Fecha y hora", event_time),
        ],
        footer_lines=[
            "Si reconoces esta solicitud, completa la verificacion desde el nuevo correo.",
            "Si no autorizaste el cambio, contactanos inmediatamente para proteger tu cuenta.",
        ],
        badge="Revision recomendada",
    )
    send_email(to_email, subject, text, html_body)


def send_account_cancellation_notification_email(
    to_email: str,
    account_name: str,
    status: str,
    admin_response: str | None = None,
) -> None:
    status_labels = {
        "approved": "Aprobada",
        "rejected": "Rechazada",
        "reviewed": "Revisada",
        "pending": "Pendiente",
    }
    label = status_labels.get(status, status)
    response_text = (admin_response or "").strip() or "No se registro una observacion adicional."
    subject = f"Aura Spa - Solicitud de cancelacion {label.lower()}"
    text = (
        f"Hola {account_name},\n\n"
        "Tu solicitud de cancelacion de inscripcion en Aura Spa fue revisada.\n\n"
        f"Estado: {label}\n"
        f"Respuesta: {response_text}\n\n"
    )
    if status == "approved":
        text += "Tu cuenta fue desactivada. Si necesitas soporte, contacta al equipo de Aura Spa."
    else:
        text += "Puedes revisar el estado desde tu perfil o contactar al equipo de Aura Spa si necesitas mas informacion."

    html_body = _build_email_layout(
        preheader="Tu solicitud de cancelacion de cuenta fue revisada por Aura Spa.",
        eyebrow="Canal de cancelacion",
        title="Resultado de tu solicitud",
        intro_lines=[
            f"Hola {account_name}, revisamos tu solicitud de cancelacion de inscripcion.",
            "Te compartimos el resultado registrado por el equipo administrador.",
        ],
        details=[
            ("Estado", label),
            ("Respuesta del equipo", response_text),
        ],
        footer_lines=[
            "Si tienes dudas sobre esta decision, puedes comunicarte con Aura Spa por los canales de contacto publicados.",
        ],
        badge=label,
        tone="success" if status == "approved" else "default",
    )
    send_email(to_email, subject, text, html_body)


def send_account_cancellation_confirmation_email(
    to_email: str,
    account_name: str,
) -> None:
    """Correo enviado al cliente cuando cancela su inscripcion de forma inmediata."""
    subject = "Aura Spa - Tu cuenta ha sido cancelada"
    text = (
        f"Hola {account_name},\n\n"
        "Confirmamos que tu inscripcion en Aura Spa ha sido cancelada exitosamente "
        "y tu cuenta ha sido desactivada.\n\n"
        "Ya no podras iniciar sesion con este correo.\n\n"
        "Si crees que esto fue un error o deseas reactivar tu cuenta, "
        "comunicate con nuestro equipo a traves de los canales de contacto "
        "publicados en nuestra plataforma.\n\n"
        "Gracias por haber sido parte de Aura Spa."
    )
    html_body = _build_email_layout(
        preheader="Tu cuenta de Aura Spa ha sido cancelada exitosamente.",
        eyebrow="Cancelacion de inscripcion",
        title="Tu cuenta ha sido cancelada",
        intro_lines=[
            f"Hola {account_name}, confirmamos que tu solicitud de cancelacion fue procesada.",
            "Tu cuenta ha sido desactivada y ya no podras iniciar sesion.",
        ],
        details=[
            ("Estado", "Cancelada"),
            ("Accion", "Cuenta desactivada"),
        ],
        footer_lines=[
            "Si crees que esto fue un error o deseas reactivar tu cuenta, contacta al equipo de Aura Spa.",
            "Gracias por haber sido parte de nuestra comunidad.",
        ],
        badge="Cancelada",
        tone="default",
    )
    send_email(to_email, subject, text, html_body)
