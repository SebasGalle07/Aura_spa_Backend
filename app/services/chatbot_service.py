import logging
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from groq import Groq
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.reservation_rules import (
    CANCELLABLE_STATUSES,
    PAYMENT_APPROVED,
    REPROGRAMMABLE_STATUSES,
    has_minimum_booking_notice,
    has_minimum_reschedule_notice,
)
from app.core.specialty_match import is_professional_compatible_with_service
from app.core.time import utc_now
from app.crud.appointment import (
    create_appointment,
    is_slot_blocked,
    list_appointments_by_client,
    list_appointments_by_professional_and_date_with_duration,
)
from app.crud.audit import (
    create_account_cancellation_request,
    get_open_account_cancellation_request,
    update_conversation_state,
)
from app.crud.company import get_or_create_company
from app.crud.professional import list_professionals
from app.crud.service import get_service, list_services
from app.crud.token import revoke_user_refresh_tokens
from app.models.audit import ChatbotConversation, ChatbotMessage
from app.models.user import User
from app.services.reservation_workflow import (
    cancel_appointment,
    initialize_payment_for_appointment,
    lock_slot_and_validate,
    prepare_pending_appointment_data,
    reschedule_appointment,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_biz() -> datetime:
    return datetime.now(ZoneInfo(settings.BUSINESS_TIMEZONE)).replace(tzinfo=None)


def _parse_date(text: str) -> str | None:
    t = text.strip().lower()
    now = _now_biz()
    if "pasado mañana" in t or "pasado manana" in t:
        return (now + timedelta(days=2)).strftime("%Y-%m-%d")
    if "mañana" in t or "manana" in t:
        return (now + timedelta(days=1)).strftime("%Y-%m-%d")
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%y"):
        try:
            return datetime.strptime(t, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _gen_slots(start: str, end: str, duration: int) -> list[str]:
    slots: list[str] = []
    sh, sm = (int(x) for x in start.split(":"))
    eh, em = (int(x) for x in end.split(":"))
    end_min = eh * 60 + em
    while sh * 60 + sm + duration <= end_min:
        slots.append(f"{sh:02d}:{sm:02d}")
        sm += duration
        if sm >= 60:
            sh += sm // 60
            sm = sm % 60
    return slots


def _to_min(t: str) -> int:
    h, m = (int(x) for x in t.split(":"))
    return h * 60 + m


def _available_slots(db: Session, professional_id: int, date: str, duration: int, sched_start: str, sched_end: str) -> list[str]:
    all_slots = _gen_slots(sched_start, sched_end, duration)
    apts = list_appointments_by_professional_and_date_with_duration(db, professional_id, date)
    result = []
    for slot in all_slots:
        if not has_minimum_booking_notice(date, slot):
            continue
        s = _to_min(slot)
        e = s + duration
        blocked = False
        for apt, apt_dur in apts:
            if not is_slot_blocked(apt):
                continue
            as_ = _to_min(apt.time)
            ae = as_ + (apt_dur or duration)
            if s < ae and as_ < e:
                blocked = True
                break
        if not blocked:
            result.append(slot)
    return result


def _is_yes(t: str) -> bool:
    return any(w in t for w in ["sí", "si", "yes", "confirmar", "confirmo", "ok", "dale", "claro", "acepto", "quiero"])


def _is_no(t: str) -> bool:
    if t.strip() == "no":
        return True
    return any(w in t for w in ["no ", "cancelar", "salir", "atras", "atrás", "regresar", "abortar"])


def _detect_intent(t: str) -> str | None:
    # Check rescheduling before booking: "reagendar" contains "agendar" as substring
    if any(w in t for w in ["reagendar", "reprogramar", "cambiar fecha", "cambiar mi cita", "cambiar la cita", "mover cita"]):
        return "rescheduling"
    if any(w in t for w in ["reservar", "agendar", "reservame", "quiero una cita", "hacer una cita", "pedir cita", "necesito una cita"]):
        return "booking"
    if any(w in t for w in ["cancelar cuenta", "cerrar cuenta", "cerrar mi cuenta", "eliminar cuenta", "dar de baja", "cancelar inscripcion", "cancelar mi cuenta", "eliminar mi cuenta"]):
        return "account_cancellation"
    if any(w in t for w in ["cancelar cita", "cancelar mi cita", "anular cita", "cancelar reserva", "anular reserva"]):
        return "cancelling"
    return None


def _pick_from_list(text: str, items: list) -> int | None:
    """Returns 0-based index from numbered input or None."""
    t = text.strip()
    try:
        idx = int(t) - 1
        if 0 <= idx < len(items):
            return idx
    except ValueError:
        pass
    return None


def _fmt_price(price) -> str:
    return f"${int(price):,} COP".replace(",", ".")


# ---------------------------------------------------------------------------
# Groq FAQ
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
Eres el asistente virtual de {business_name}, un spa ubicado en {city}, Colombia.

Información del negocio:
- Dirección: {address}
- Teléfono: {phone}
- Horario: Lunes–viernes {week_start}–{week_end} | Sábados {sat_start}–{sat_end} | Domingos {sun_start}–{sun_end}
{user_line}

Servicios disponibles:
{services_text}

Políticas:
- Las reservas requieren un anticipo del 30 % del precio; el cupo queda bloqueado 15 minutos mientras se paga.
- El anticipo no es reembolsable.
- Cancelaciones con mínimo 48 horas de anticipación.
- Reprogramaciones solo para reservas confirmadas con pago aprobado y con mínimo 48 horas de anticipación.
- Para reservar el cliente debe iniciar sesión y puede pedirle ayuda al chatbot.

Instrucciones:
- Responde siempre en español, de forma breve y amable.
- Solo responde preguntas relacionadas con el spa.
- No inventes información que no esté en este contexto.\
"""


def _build_system_prompt(company, services, user: User | None) -> str:
    services_text = "\n".join(
        f"- {s.name} ({s.category}): {_fmt_price(s.price)}, {s.duration} min"
        for s in services
    ) or "No hay servicios activos."
    user_line = (
        f"- Usuario autenticado: {user.name} ({user.email})"
        if user else "- El usuario no ha iniciado sesión."
    )
    return _SYSTEM_PROMPT.format(
        business_name=company.business_name or "Aura Spa",
        city=company.city or "Armenia",
        address=(company.address or "No disponible").replace("\n", ", "),
        phone=company.phone or company.whatsapp or "No disponible",
        week_start=company.week_start or "09:00",
        week_end=company.week_end or "18:00",
        sat_start=company.sat_start or "09:00",
        sat_end=company.sat_end or "18:00",
        sun_start=company.sun_start or "10:00",
        sun_end=company.sun_end or "17:00",
        user_line=user_line,
        services_text=services_text,
    )


def _groq_faq(message: str, system_prompt: str, history: list[ChatbotMessage]) -> str | None:
    if not settings.GROQ_API_KEY:
        return None
    try:
        client = Groq(api_key=settings.GROQ_API_KEY)
        messages: list[dict] = [{"role": "system", "content": system_prompt}]
        for msg in history[-10:]:
            role = "user" if msg.sender == "user" else "assistant"
            messages.append({"role": role, "content": msg.message})
        messages.append({"role": "user", "content": message})
        completion = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            max_tokens=settings.GROQ_MAX_TOKENS,
            temperature=0.4,
        )
        return completion.choices[0].message.content.strip()
    except Exception as exc:
        logger.warning("Groq API error: %s", exc)
        return None


def _keyword_faq(text: str, company, services, user: User | None) -> str:
    matched = next((s for s in services if s.name.strip().lower() in text), None)
    if any(w in text for w in ["hola", "buenas", "saludos"]):
        name = f", {user.name}" if user else ""
        return (f"Hola{name}, soy el asistente de {company.business_name or 'Aura Spa'}. "
                "Puedo ayudarte con información, reservas, cancelaciones y reprogramaciones.")
    if matched and any(w in text for w in ["precio", "costo", "cuanto", "vale", "dura"]):
        return (f"{matched.name} cuesta {_fmt_price(matched.price)} y dura {matched.duration} min. "
                "Para reservarlo escribe 'quiero una cita'.")
    if any(w in text for w in ["servicio", "servicios", "precio", "precios", "costo"]):
        if not services:
            return "En este momento no hay servicios activos."
        lines = [f"- {s.name}: {_fmt_price(s.price)}, {s.duration} min" for s in services[:5]]
        extra = "\nHay más servicios en el catálogo." if len(services) > 5 else ""
        return "Servicios disponibles:\n" + "\n".join(lines) + extra
    if any(w in text for w in ["pago", "anticipo", "pasarela"]):
        return "Las reservas requieren un anticipo del 30 %. El saldo se paga al momento de la atención."
    if any(w in text for w in ["horario", "ubicacion", "telefono", "contacto"]):
        phone = company.phone or company.whatsapp or "ver sección de contacto"
        return (f"Horario: lunes–viernes {company.week_start or '09:00'}–{company.week_end or '18:00'}, "
                f"sábados {company.sat_start or '09:00'}–{company.sat_end or '18:00'}. Tel: {phone}.")
    return ("Puedo ayudarte con servicios, precios, reservas, cancelaciones, reprogramaciones y contacto. "
            "¿En qué te puedo ayudar?")


# ---------------------------------------------------------------------------
# State machine — BOOKING
# ---------------------------------------------------------------------------

def _handle_booking(db: Session, text: str, state: dict, user: User, conversation_id: int) -> str:
    data = state.setdefault("data", {})
    step = state.get("step", "selecting_service")
    services = [s for s in list_services(db) if s.active]

    if step == "selecting_service":
        idx = _pick_from_list(text, services)
        if idx is None:
            for s in services:
                if s.name.strip().lower() in text:
                    idx = services.index(s)
                    break
        if idx is None:
            lines = [f"{i+1}. {s.name} — {_fmt_price(s.price)}, {s.duration} min" for i, s in enumerate(services)]
            return "¿Qué servicio deseas?\n" + "\n".join(lines)

        service = services[idx]
        professionals = [
            p for p in list_professionals(db, active=True)
            if is_professional_compatible_with_service(service.category, p.specialty)
        ]
        if not professionals:
            update_conversation_state(db, conversation_id, None)
            return f"Lo sentimos, no hay profesionales disponibles para {service.name} en este momento."

        prof = professionals[0]
        data.update({
            "service_id": service.id,
            "service_name": service.name,
            "service_price": service.price,
            "service_duration": service.duration,
            "professional_id": prof.id,
            "professional_name": prof.name,
            "sched_start": prof.schedule_start,
            "sched_end": prof.schedule_end,
        })
        state["step"] = "selecting_date"
        update_conversation_state(db, conversation_id, state)
        return (f"Servicio: {service.name} con {prof.name}.\n"
                "¿Qué fecha prefieres? (DD/MM/AAAA o escribe 'mañana')\n"
                "Escribe 'salir' para cancelar.")

    if step == "selecting_date":
        date_str = _parse_date(text)
        if not date_str:
            return "No entendí la fecha. Usa DD/MM/AAAA (ej: 20/05/2026) o 'mañana'."
        if date_str < _now_biz().strftime("%Y-%m-%d"):
            return "La fecha no puede ser en el pasado. Intenta con otra fecha."
        slots = _available_slots(
            db, data["professional_id"], date_str,
            data["service_duration"], data["sched_start"], data["sched_end"],
        )
        if not slots:
            return f"No hay horarios disponibles el {date_str}. Prueba con otra fecha."
        data["date"] = date_str
        data["available_slots"] = slots
        state["step"] = "selecting_time"
        update_conversation_state(db, conversation_id, state)
        lines = [f"{i+1}. {s}" for i, s in enumerate(slots)]
        return f"Horarios disponibles para el {date_str}:\n" + "\n".join(lines) + "\n¿Cuál prefieres?"

    if step == "selecting_time":
        slots = data.get("available_slots", [])
        idx = _pick_from_list(text, slots)
        if idx is None:
            t = text.strip()
            if t in slots:
                idx = slots.index(t)
        if idx is None:
            lines = [f"{i+1}. {s}" for i, s in enumerate(slots)]
            return "No entendí el horario. Elige un número:\n" + "\n".join(lines)
        data["time"] = slots[idx]
        state["step"] = "confirming"
        update_conversation_state(db, conversation_id, state)
        deposit = int(Decimal(str(data["service_price"])) * Decimal("0.30"))
        return (
            f"Resumen de tu reserva:\n"
            f"- Servicio: {data['service_name']}\n"
            f"- Profesional: {data['professional_name']}\n"
            f"- Fecha: {data['date']}  Hora: {data['time']}\n"
            f"- Anticipo: {_fmt_price(deposit)} (30 %)\n\n"
            "¿Confirmas? (responde 'sí' o 'no')"
        )

    if step == "confirming":
        if _is_no(text) or text == "no":
            update_conversation_state(db, conversation_id, None)
            return "Reserva cancelada. ¿En qué más puedo ayudarte?"
        if not _is_yes(text):
            return "Por favor responde 'sí' para confirmar o 'no' para cancelar."

        if not user.phone or not user.phone.isdigit() or len(user.phone) != 10:
            update_conversation_state(db, conversation_id, None)
            return ("Para reservar necesitas un teléfono colombiano de 10 dígitos en tu perfil. "
                    "Actualízalo en la sección 'Mi perfil' e intenta de nuevo.")

        service = get_service(db, data["service_id"])
        try:
            appointment_data = prepare_pending_appointment_data(
                service,
                client_user_id=user.id,
                client_name=user.name,
                client_email=user.email,
                client_phone=user.phone,
                professional_id=data["professional_id"],
                date=data["date"],
                time=data["time"],
            )
            lock_slot_and_validate(
                db,
                professional_id=data["professional_id"],
                date=data["date"],
                time=data["time"],
                service_duration=data["service_duration"],
            )
            appointment = create_appointment(db, appointment_data)
            initialize_payment_for_appointment(db, appointment)
            db.commit()
        except HTTPException as exc:
            update_conversation_state(db, conversation_id, None)
            return f"No se pudo crear la reserva: {exc.detail}. Intenta con otra fecha u hora."
        except Exception as exc:
            db.rollback()
            update_conversation_state(db, conversation_id, None)
            logger.exception("Error creando reserva desde chatbot: %s", exc)
            return "Ocurrió un error al crear la reserva. Intenta desde el módulo de reservas."

        update_conversation_state(db, conversation_id, None)
        return (
            f"✓ Reserva creada exitosamente (ID #{appointment.id}).\n"
            f"Tienes 15 minutos para completar el pago del anticipo.\n"
            "Ve a 'Mis Citas' → selecciona la reserva → 'Pagar anticipo'."
        )

    update_conversation_state(db, conversation_id, None)
    return "Ocurrió un error en el flujo. Escribe 'reservar' para comenzar de nuevo."


# ---------------------------------------------------------------------------
# State machine — CANCELLING
# ---------------------------------------------------------------------------

def _handle_cancelling(db: Session, text: str, state: dict, user: User, conversation_id: int) -> str:
    data = state.setdefault("data", {})
    step = state.get("step", "selecting_appointment")

    if step == "selecting_appointment":
        appointments = [
            a for a in list_appointments_by_client(db, user.id, user.email)
            if a.status in CANCELLABLE_STATUSES
        ]
        if not appointments:
            update_conversation_state(db, conversation_id, None)
            return "No tienes citas activas que se puedan cancelar."

        idx = _pick_from_list(text, appointments)
        if idx is None:
            lines = [
                f"{i+1}. #{a.id} — {a.date} {a.time} (estado: {a.status})"
                for i, a in enumerate(appointments)
            ]
            return "¿Cuál cita deseas cancelar?\n" + "\n".join(lines)

        apt = appointments[idx]
        if not has_minimum_reschedule_notice(apt.date, apt.time):
            update_conversation_state(db, conversation_id, None)
            return (f"La cita del {apt.date} a las {apt.time} no puede cancelarse "
                    "porque es en menos de 48 horas.")

        data["appointment_id"] = apt.id
        data["apt_summary"] = f"{apt.date} a las {apt.time}"
        state["step"] = "confirming"
        update_conversation_state(db, conversation_id, state)
        return (f"¿Confirmas la cancelación de la cita del {apt.date} a las {apt.time}?\n"
                "Recuerda: el anticipo no es reembolsable.\n"
                "Responde 'sí' o 'no'.")

    if step == "confirming":
        if _is_no(text) or text == "no":
            update_conversation_state(db, conversation_id, None)
            return "Cancelación abortada. ¿En qué más puedo ayudarte?"
        if not _is_yes(text):
            return "Responde 'sí' para confirmar o 'no' para cancelar."

        from app.crud.appointment import get_appointment_for_update
        try:
            apt = get_appointment_for_update(db, data["appointment_id"])
            cancel_appointment(db, apt, actor_type="client", actor_id=user.id, reason="Cancelada via chatbot")
            db.commit()
        except HTTPException as exc:
            update_conversation_state(db, conversation_id, None)
            return f"No se pudo cancelar: {exc.detail}"
        except Exception as exc:
            db.rollback()
            update_conversation_state(db, conversation_id, None)
            logger.exception("Error cancelando desde chatbot: %s", exc)
            return "Ocurrió un error. Intenta desde 'Mis Citas'."

        update_conversation_state(db, conversation_id, None)
        return f"✓ Cita del {data['apt_summary']} cancelada correctamente."

    update_conversation_state(db, conversation_id, None)
    return "Ocurrió un error. Escribe 'cancelar cita' para comenzar de nuevo."


# ---------------------------------------------------------------------------
# State machine — RESCHEDULING
# ---------------------------------------------------------------------------

def _handle_rescheduling(db: Session, text: str, state: dict, user: User, conversation_id: int) -> str:
    data = state.setdefault("data", {})
    step = state.get("step", "selecting_appointment")

    if step == "selecting_appointment":
        appointments = [
            a for a in list_appointments_by_client(db, user.id, user.email)
            if a.status in REPROGRAMMABLE_STATUSES and a.payment_status == PAYMENT_APPROVED
        ]
        if not appointments:
            update_conversation_state(db, conversation_id, None)
            return ("No tienes citas reprogramables. Solo se pueden reprogramar citas "
                    "confirmadas con pago aprobado.")

        idx = _pick_from_list(text, appointments)
        if idx is None:
            lines = [
                f"{i+1}. #{a.id} — {a.date} {a.time} (estado: {a.status})"
                for i, a in enumerate(appointments)
            ]
            return "¿Cuál cita deseas reprogramar?\n" + "\n".join(lines)

        apt = appointments[idx]
        if not has_minimum_reschedule_notice(apt.date, apt.time):
            update_conversation_state(db, conversation_id, None)
            return (f"La cita del {apt.date} a las {apt.time} no puede reprogramarse "
                    "porque es en menos de 48 horas.")

        service = get_service(db, apt.service_id)
        data.update({
            "appointment_id": apt.id,
            "service_duration": service.duration if service else 60,
            "apt_summary": f"{apt.date} a las {apt.time}",
        })
        state["step"] = "selecting_date"
        update_conversation_state(db, conversation_id, state)
        return (f"Reprogramando cita del {apt.date} a las {apt.time}.\n"
                "¿Cuál es la nueva fecha? (DD/MM/AAAA o 'mañana')")

    if step == "selecting_date":
        date_str = _parse_date(text)
        if not date_str:
            return "No entendí la fecha. Usa DD/MM/AAAA (ej: 20/05/2026) o 'mañana'."
        if date_str < _now_biz().strftime("%Y-%m-%d"):
            return "La fecha no puede ser en el pasado."

        from app.crud.appointment import get_appointment
        apt = get_appointment(db, data["appointment_id"])
        if not apt:
            update_conversation_state(db, conversation_id, None)
            return "No encontré la cita. Intenta de nuevo."

        service = get_service(db, apt.service_id)
        from app.crud.professional import get_professional
        prof = get_professional(db, apt.professional_id)
        slots = _available_slots(
            db, apt.professional_id, date_str,
            data["service_duration"],
            prof.schedule_start if prof else "08:00",
            prof.schedule_end if prof else "18:00",
        )
        if not slots:
            return f"No hay horarios disponibles el {date_str}. Prueba con otra fecha."

        data["new_date"] = date_str
        data["available_slots"] = slots
        state["step"] = "selecting_time"
        update_conversation_state(db, conversation_id, state)
        lines = [f"{i+1}. {s}" for i, s in enumerate(slots)]
        return f"Horarios disponibles para el {date_str}:\n" + "\n".join(lines) + "\n¿Cuál prefieres?"

    if step == "selecting_time":
        slots = data.get("available_slots", [])
        idx = _pick_from_list(text, slots)
        if idx is None and text.strip() in slots:
            idx = slots.index(text.strip())
        if idx is None:
            lines = [f"{i+1}. {s}" for i, s in enumerate(slots)]
            return "Elige un número:\n" + "\n".join(lines)
        data["new_time"] = slots[idx]
        state["step"] = "confirming"
        update_conversation_state(db, conversation_id, state)
        return (f"¿Confirmas el cambio de cita?\n"
                f"- Fecha anterior: {data['apt_summary']}\n"
                f"- Nueva fecha: {data['new_date']} a las {data['new_time']}\n"
                "Responde 'sí' o 'no'.")

    if step == "confirming":
        if _is_no(text) or text == "no":
            update_conversation_state(db, conversation_id, None)
            return "Reprogramación cancelada. ¿En qué más puedo ayudarte?"
        if not _is_yes(text):
            return "Responde 'sí' para confirmar o 'no' para cancelar."

        from app.crud.appointment import get_appointment_for_update
        try:
            apt = get_appointment_for_update(db, data["appointment_id"])
            reschedule_appointment(
                db, apt,
                service_duration=data["service_duration"],
                new_date=data["new_date"],
                new_time=data["new_time"],
                actor_type="client",
                actor_id=user.id,
                reason="Reprogramada via chatbot",
            )
            db.commit()
        except HTTPException as exc:
            update_conversation_state(db, conversation_id, None)
            return f"No se pudo reprogramar: {exc.detail}"
        except Exception as exc:
            db.rollback()
            update_conversation_state(db, conversation_id, None)
            logger.exception("Error reprogramando desde chatbot: %s", exc)
            return "Ocurrió un error. Intenta desde 'Mis Citas'."

        update_conversation_state(db, conversation_id, None)
        return f"✓ Cita reprogramada para el {data['new_date']} a las {data['new_time']}."

    update_conversation_state(db, conversation_id, None)
    return "Ocurrió un error. Escribe 'reagendar' para comenzar de nuevo."


# ---------------------------------------------------------------------------
# State machine — ACCOUNT CANCELLATION
# ---------------------------------------------------------------------------

def _handle_account_cancellation(db: Session, text: str, state: dict, user: User, conversation_id: int) -> str:
    data = state.setdefault("data", {})
    step = state.get("step", "entering_reason")

    if step == "entering_reason":
        reason = text.strip()
        if len(reason) < 10:
            return ("Por favor describe el motivo de cancelación "
                    "(mínimo 10 caracteres). Escribe 'no' para cancelar.")
        data["reason"] = reason
        state["step"] = "confirming"
        update_conversation_state(db, conversation_id, state)
        return ("⚠ Esta acción es IRREVERSIBLE. Tu cuenta quedará desactivada de inmediato "
                "y perderás acceso a tu historial.\n"
                "¿Confirmas la cancelación? Responde 'sí' o 'no'.")

    if step == "confirming":
        if _is_no(text) or text == "no":
            update_conversation_state(db, conversation_id, None)
            return "Cancelación de cuenta abortada. ¿En qué más puedo ayudarte?"
        if not _is_yes(text):
            return "Responde 'sí' para confirmar la cancelación o 'no' para cancelar."

        existing = get_open_account_cancellation_request(db, user.id)
        if existing:
            update_conversation_state(db, conversation_id, None)
            return "Tu cuenta ya fue cancelada o tiene una solicitud en proceso."

        try:
            now = utc_now()
            create_account_cancellation_request(
                db, user_id=user.id, reason=data["reason"],
                status="approved", reviewed_at=now,
            )
            from app.crud.user import get_user_by_id
            db_user = get_user_by_id(db, user.id)
            if db_user:
                db_user.is_active = False
                db_user.deactivated_at = now
                db.add(db_user)
            revoke_user_refresh_tokens(db, user.id)
            db.commit()
        except Exception as exc:
            db.rollback()
            update_conversation_state(db, conversation_id, None)
            logger.exception("Error cancelando cuenta desde chatbot: %s", exc)
            return "Ocurrió un error. Intenta desde 'Mi perfil'."

        update_conversation_state(db, conversation_id, None)
        return ("✓ Tu cuenta ha sido cancelada. Cierra sesión para finalizar el proceso. "
                "Si en el futuro deseas volver, puedes registrarte con el mismo correo.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_contextual_response(
    db: Session,
    message: str,
    *,
    history: list[ChatbotMessage] | None = None,
    user: User | None = None,
    conversation: ChatbotConversation | None = None,
) -> str:
    history = history or []
    text = message.strip().lower()

    # --- Abort active flow ---
    if conversation and conversation.booking_state and _is_no(text):
        update_conversation_state(db, conversation.id, None)
        return "Operación cancelada. ¿En qué más puedo ayudarte?"

    # --- Continue active flow ---
    if conversation and conversation.booking_state:
        state = dict(conversation.booking_state)
        action = state.get("action")

        if not user:
            update_conversation_state(db, conversation.id, None)
            return "Tu sesión ha expirado. Por favor inicia sesión para continuar."

        if action == "booking":
            return _handle_booking(db, text, state, user, conversation.id)
        if action == "cancelling":
            return _handle_cancelling(db, text, state, user, conversation.id)
        if action == "rescheduling":
            return _handle_rescheduling(db, text, state, user, conversation.id)
        if action == "account_cancellation":
            return _handle_account_cancellation(db, text, state, user, conversation.id)

    # --- Detect new intent ---
    intent = _detect_intent(text)
    if intent:
        if not user:
            return "Para realizar esta acción necesitas iniciar sesión primero."

        new_state: dict = {"action": intent, "step": "", "data": {}}

        if intent == "booking":
            services = [s for s in list_services(db) if s.active]
            if not services:
                return "En este momento no hay servicios disponibles."
            new_state["step"] = "selecting_service"
            update_conversation_state(db, conversation.id, new_state)
            lines = [f"{i+1}. {s.name} — {_fmt_price(s.price)}, {s.duration} min" for i, s in enumerate(services)]
            return (f"Con gusto te ayudo a reservar, {user.name}.\n"
                    "¿Qué servicio deseas?\n" + "\n".join(lines) +
                    "\n\nEscribe 'salir' en cualquier momento para cancelar.")

        if intent == "cancelling":
            appointments = [
                a for a in list_appointments_by_client(db, user.id, user.email)
                if a.status in CANCELLABLE_STATUSES
            ]
            if not appointments:
                return "No tienes citas activas que se puedan cancelar."
            new_state["step"] = "selecting_appointment"
            update_conversation_state(db, conversation.id, new_state)
            lines = [
                f"{i+1}. #{a.id} — {a.date} {a.time} (estado: {a.status})"
                for i, a in enumerate(appointments)
            ]
            return "¿Cuál cita deseas cancelar?\n" + "\n".join(lines)

        if intent == "rescheduling":
            appointments = [
                a for a in list_appointments_by_client(db, user.id, user.email)
                if a.status in REPROGRAMMABLE_STATUSES and a.payment_status == PAYMENT_APPROVED
            ]
            if not appointments:
                return ("No tienes citas reprogramables. Solo se pueden reprogramar citas "
                        "confirmadas con pago aprobado.")
            new_state["step"] = "selecting_appointment"
            update_conversation_state(db, conversation.id, new_state)
            lines = [
                f"{i+1}. #{a.id} — {a.date} {a.time} (estado: {a.status})"
                for i, a in enumerate(appointments)
            ]
            return "¿Cuál cita deseas reprogramar?\n" + "\n".join(lines)

        if intent == "account_cancellation":
            new_state["step"] = "entering_reason"
            update_conversation_state(db, conversation.id, new_state)
            return ("Voy a ayudarte a cancelar tu cuenta.\n"
                    "Por favor indica el motivo de cancelación (mínimo 10 caracteres).\n"
                    "Escribe 'no' para cancelar.")

    # --- FAQ via Groq or keyword fallback ---
    company = get_or_create_company(db)
    services = [s for s in list_services(db) if s.active]
    system_prompt = _build_system_prompt(company, services, user)
    groq_reply = _groq_faq(message, system_prompt, history)
    if groq_reply:
        return groq_reply
    return _keyword_faq(text, company, services, user)
