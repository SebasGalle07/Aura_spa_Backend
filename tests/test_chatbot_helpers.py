"""Unit tests for chatbot_service pure helper functions."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_unit.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only-32chars")
os.environ.setdefault("GROQ_API_KEY", "")

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.services.chatbot_service import (
    _detect_intent,
    _is_no,
    _is_yes,
    _parse_date,
    _pick_from_list,
    _fmt_price,
    _gen_slots,
    _to_min,
)


# ---------------------------------------------------------------------------
# _fmt_price
# ---------------------------------------------------------------------------

def test_fmt_price_integer():
    assert _fmt_price(120000) == "$120.000 COP"


def test_fmt_price_zero():
    assert _fmt_price(0) == "$0 COP"


# ---------------------------------------------------------------------------
# _to_min / _gen_slots
# ---------------------------------------------------------------------------

def test_to_min():
    assert _to_min("09:00") == 540
    assert _to_min("10:30") == 630
    assert _to_min("00:00") == 0


def test_gen_slots_60min():
    slots = _gen_slots("09:00", "12:00", 60)
    assert slots == ["09:00", "10:00", "11:00"]


def test_gen_slots_45min():
    # 10:30 + 45min = 11:15 > 11:00, so only 09:00 and 09:45 fit
    slots = _gen_slots("09:00", "11:00", 45)
    assert slots == ["09:00", "09:45"]


def test_gen_slots_no_slots_when_duration_exceeds_window():
    slots = _gen_slots("09:00", "09:30", 60)
    assert slots == []


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

FIXED_NOW = datetime(2026, 5, 10, 10, 0, 0)


def _patched_parse(text: str) -> str | None:
    with patch("app.services.chatbot_service._now_biz", return_value=FIXED_NOW):
        return _parse_date(text)


def test_parse_date_manana():
    result = _patched_parse("mañana")
    assert result == "2026-05-11"


def test_parse_date_pasado_manana():
    result = _patched_parse("pasado mañana")
    assert result == "2026-05-12"


def test_parse_date_ddmmyyyy():
    assert _parse_date("20/05/2026") == "2026-05-20"


def test_parse_date_with_dashes():
    assert _parse_date("20-05-2026") == "2026-05-20"


def test_parse_date_iso():
    assert _parse_date("2026-05-20") == "2026-05-20"


def test_parse_date_invalid():
    assert _parse_date("hoy en la tarde") is None
    assert _parse_date("no se") is None
    assert _parse_date("") is None


# ---------------------------------------------------------------------------
# _is_yes / _is_no
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["sí", "si", "yes", "confirmar", "confirmo", "ok", "dale", "claro", "acepto", "quiero"])
def test_is_yes(text):
    assert _is_yes(text) is True


@pytest.mark.parametrize("text", ["no", "no quiero", "cancelar", "salir", "atras", "atrás", "regresar", "abortar"])
def test_is_no(text):
    assert _is_no(text) is True


def test_is_yes_does_not_match_no():
    assert _is_yes("no") is False


def test_is_no_does_not_match_yes():
    assert _is_no("sí") is False


# ---------------------------------------------------------------------------
# _detect_intent
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("quiero reservar una cita", "booking"),
    ("reservame una cita para mañana", "booking"),
    ("necesito una cita", "booking"),
    ("quiero agendar", "booking"),
    ("cancelar mi cita del jueves", "cancelling"),
    ("quiero cancelar mi cita", "cancelling"),
    ("anular reserva", "cancelling"),
    ("reagendar mi cita", "rescheduling"),
    ("reprogramar la cita", "rescheduling"),
    ("cambiar fecha de mi cita", "rescheduling"),
    ("cancelar mi cuenta", "account_cancellation"),
    ("quiero cerrar mi cuenta", "account_cancellation"),
    ("eliminar mi cuenta", "account_cancellation"),
    ("dar de baja", "account_cancellation"),
])
def test_detect_intent(text, expected):
    assert _detect_intent(text.lower()) == expected


@pytest.mark.parametrize("text", [
    "cuanto cuesta el masaje",
    "cuáles son los servicios",
    "cuál es el horario",
    "hola",
    "información de contacto",
])
def test_detect_intent_faq_returns_none(text):
    assert _detect_intent(text.lower()) is None


# ---------------------------------------------------------------------------
# _pick_from_list
# ---------------------------------------------------------------------------

def test_pick_from_list_by_number():
    items = ["a", "b", "c"]
    assert _pick_from_list("1", items) == 0
    assert _pick_from_list("2", items) == 1
    assert _pick_from_list("3", items) == 2


def test_pick_from_list_out_of_range():
    items = ["a", "b"]
    assert _pick_from_list("5", items) is None
    assert _pick_from_list("0", items) is None


def test_pick_from_list_non_numeric():
    items = ["a", "b"]
    assert _pick_from_list("texto", items) is None
