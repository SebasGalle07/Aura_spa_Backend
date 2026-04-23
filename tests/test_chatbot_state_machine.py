"""Unit tests for chatbot state machine intent detection and flow control."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_unit.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only-32chars")
os.environ.setdefault("GROQ_API_KEY", "")

import pytest
from unittest.mock import MagicMock, patch

from app.services.chatbot_service import (
    _detect_intent,
    _is_yes,
    _is_no,
    _parse_date,
    _pick_from_list,
    build_contextual_response,
)


# ---------------------------------------------------------------------------
# Unauthenticated user — action intents require login
# ---------------------------------------------------------------------------

def test_booking_intent_requires_login():
    db = MagicMock()
    conversation = MagicMock()
    conversation.booking_state = None

    with patch("app.services.chatbot_service.get_or_create_company"), \
         patch("app.services.chatbot_service.list_services", return_value=[]), \
         patch("app.services.chatbot_service._groq_faq", return_value=None):
        response = build_contextual_response(
            db, "quiero reservar una cita",
            user=None,
            conversation=conversation,
        )
    assert "iniciar sesión" in response.lower() or "inicia sesión" in response.lower()


def test_cancelling_intent_requires_login():
    db = MagicMock()
    conversation = MagicMock()
    conversation.booking_state = None

    with patch("app.services.chatbot_service.get_or_create_company"), \
         patch("app.services.chatbot_service.list_services", return_value=[]), \
         patch("app.services.chatbot_service._groq_faq", return_value=None):
        response = build_contextual_response(
            db, "cancelar mi cita",
            user=None,
            conversation=conversation,
        )
    assert "iniciar sesión" in response.lower() or "inicia sesión" in response.lower()


# ---------------------------------------------------------------------------
# Booking flow — first step shows service list
# ---------------------------------------------------------------------------

def test_booking_intent_shows_service_list():
    db = MagicMock()
    conversation = MagicMock()
    conversation.booking_state = None
    conversation.id = 1

    mock_service = MagicMock()
    mock_service.id = 1
    mock_service.name = "Masaje Relajante"
    mock_service.price = 120000
    mock_service.duration = 60
    mock_service.active = True

    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.name = "Juan"
    mock_user.email = "juan@test.com"

    with patch("app.services.chatbot_service.list_services", return_value=[mock_service]), \
         patch("app.services.chatbot_service.update_conversation_state"):
        response = build_contextual_response(
            db, "quiero reservar una cita",
            user=mock_user,
            conversation=conversation,
        )

    assert "Masaje Relajante" in response
    assert "1." in response


# ---------------------------------------------------------------------------
# Abort active flow with "no" / "salir"
# ---------------------------------------------------------------------------

def test_abort_active_flow():
    db = MagicMock()
    conversation = MagicMock()
    conversation.booking_state = {"action": "booking", "step": "selecting_service", "data": {}}
    conversation.id = 1
    mock_user = MagicMock()
    mock_user.id = 1

    with patch("app.services.chatbot_service.update_conversation_state") as mock_update:
        response = build_contextual_response(
            db, "no",
            user=mock_user,
            conversation=conversation,
        )

    mock_update.assert_called_once_with(db, 1, None)
    assert "cancelad" in response.lower()


# ---------------------------------------------------------------------------
# Account cancellation flow — reason too short
# ---------------------------------------------------------------------------

def test_account_cancellation_reason_too_short():
    db = MagicMock()
    conversation = MagicMock()
    conversation.id = 1
    conversation.booking_state = {
        "action": "account_cancellation",
        "step": "entering_reason",
        "data": {},
    }

    mock_user = MagicMock()
    mock_user.id = 1

    with patch("app.services.chatbot_service.update_conversation_state"):
        response = build_contextual_response(
            db, "corto",
            user=mock_user,
            conversation=conversation,
        )

    assert "10 caracteres" in response or "mínimo" in response.lower()


# ---------------------------------------------------------------------------
# Cancelling flow — no active appointments
# ---------------------------------------------------------------------------

def test_cancelling_no_active_appointments():
    db = MagicMock()
    conversation = MagicMock()
    conversation.id = 1
    conversation.booking_state = None

    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.email = "u@test.com"
    mock_user.name = "User"

    with patch("app.services.chatbot_service.list_appointments_by_client", return_value=[]), \
         patch("app.services.chatbot_service.update_conversation_state"):
        response = build_contextual_response(
            db, "cancelar mi cita",
            user=mock_user,
            conversation=conversation,
        )

    assert "no tienes" in response.lower() or "no hay" in response.lower()


# ---------------------------------------------------------------------------
# Rescheduling flow — no reschedulable appointments
# ---------------------------------------------------------------------------

def test_rescheduling_no_eligible_appointments():
    db = MagicMock()
    conversation = MagicMock()
    conversation.id = 1
    conversation.booking_state = None

    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.email = "u@test.com"

    with patch("app.services.chatbot_service.list_appointments_by_client", return_value=[]), \
         patch("app.services.chatbot_service.update_conversation_state"):
        response = build_contextual_response(
            db, "reagendar mi cita",
            user=mock_user,
            conversation=conversation,
        )

    assert "no tienes" in response.lower() or "no hay" in response.lower()


# ---------------------------------------------------------------------------
# Booking — no services available
# ---------------------------------------------------------------------------

def test_booking_no_services():
    db = MagicMock()
    conversation = MagicMock()
    conversation.id = 1
    conversation.booking_state = None

    mock_user = MagicMock()
    mock_user.id = 1

    with patch("app.services.chatbot_service.list_services", return_value=[]), \
         patch("app.services.chatbot_service.update_conversation_state"):
        response = build_contextual_response(
            db, "quiero agendar una cita",
            user=mock_user,
            conversation=conversation,
        )

    assert "no hay" in response.lower() or "disponibles" in response.lower()
