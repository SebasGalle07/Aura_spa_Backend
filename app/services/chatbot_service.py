from sqlalchemy.orm import Session

from app.crud.company import get_or_create_company
from app.crud.service import list_services
from app.models.audit import ChatbotMessage
from app.models.user import User


def _normalize(value: str) -> str:
    return value.strip().lower()


def _detect_service_name(message: str, services, history: list[ChatbotMessage]) -> str | None:
    text = _normalize(message)
    for service in services:
        if _normalize(service.name) in text:
            return service.name

    for previous in reversed(history):
        previous_text = _normalize(previous.message)
        for service in services:
            if _normalize(service.name) in previous_text:
                return service.name
    return None


def build_contextual_response(
    db: Session,
    message: str,
    *,
    history: list[ChatbotMessage] | None = None,
    user: User | None = None,
) -> str:
    history = history or []
    text = message.strip().lower()
    company = get_or_create_company(db)
    services = [svc for svc in list_services(db) if svc.active]
    matched_service_name = _detect_service_name(message, services, history)
    matched_service = next((svc for svc in services if svc.name == matched_service_name), None)

    if any(word in text for word in ["hola", "buenas", "saludos"]):
        greeting_name = f", {user.name}" if user else ""
        return (
            f"Hola{greeting_name}, soy el asistente virtual de {company.business_name or 'Aura Spa'}. "
            "Puedo ayudarte con servicios, reservas, pagos, cancelaciones y reprogramaciones."
        )

    if matched_service and any(word in text for word in ["precio", "precios", "costo", "cuanto", "vale", "dura"]):
        return (
            f"El servicio {matched_service.name} cuesta ${int(matched_service.price):,} COP "
            f"y tiene una duracion de {matched_service.duration} minutos. "
            "Para reservarlo, inicia sesion y selecciona servicio, profesional, fecha y hora."
        ).replace(",", ".")

    if any(word in text for word in ["servicio", "servicios", "precio", "precios", "costo"]):
        if not services:
            return "En este momento no hay servicios activos publicados. Intenta nuevamente mas tarde."
        preview = services[:5]
        lines = [f"- {svc.name}: ${int(svc.price):,} COP, duracion {svc.duration} min" for svc in preview]
        suffix = "" if len(services) <= 5 else "\nTambien tenemos mas servicios disponibles en el catalogo."
        return "Estos son algunos servicios disponibles:\n" + "\n".join(lines).replace(",", ".") + suffix

    if any(word in text for word in ["reserv", "cita", "agendar", "agenda"]):
        if matched_service:
            return (
                f"Para reservar {matched_service.name}, selecciona ese servicio en el modulo de reservas, "
                "elige profesional, fecha y hora. El cupo queda bloqueado temporalmente mientras pagas el anticipo."
            )
        return (
            "Para reservar debes iniciar sesion, elegir servicio, profesional, fecha y hora. "
            "El sistema bloquea temporalmente el cupo mientras realizas el pago del anticipo."
        )

    if any(word in text for word in ["pago", "anticipo", "payu", "pasarela"]):
        return (
            "Las reservas se confirman con el pago de un anticipo mediante la pasarela de pagos en modo prueba. "
            "El saldo restante se paga posteriormente segun las condiciones del servicio."
        )

    if any(word in text for word in ["cancel", "reembolso", "devolver"]):
        return (
            "Puedes cancelar con al menos 48 horas de anticipacion. "
            "El anticipo de reserva no es reembolsable porque garantiza el cupo apartado."
        )

    if any(word in text for word in ["reprogram", "cambiar fecha", "cambiar hora"]):
        return (
            "La reprogramacion solo aplica para reservas confirmadas con pago aprobado y debe solicitarse "
            "con minimo 48 horas de anticipacion."
        )

    if any(word in text for word in ["horario", "ubicacion", "telefono", "contacto"]):
        schedule = f"Lunes a viernes {company.week_start or '09:00'} - {company.week_end or '18:00'}"
        phone = company.phone or company.whatsapp or "el numero publicado en la seccion de contacto"
        return f"Nuestro horario general es: {schedule}. Puedes contactarnos por telefono al {phone}."

    return (
        "Puedo ayudarte con servicios, reservas, pagos, cancelaciones, reprogramaciones y datos de contacto. "
        "Escribe tu pregunta con una de esas palabras clave para darte una respuesta mas precisa."
    )
