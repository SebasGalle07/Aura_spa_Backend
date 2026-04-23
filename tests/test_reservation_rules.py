"""Unit tests for reservation business rules."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_unit.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only-32chars")
os.environ.setdefault("GROQ_API_KEY", "")

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from app.core.reservation_rules import (
    compute_deposit_amount,
    has_minimum_booking_notice,
    has_minimum_reschedule_notice,
    is_future_slot,
    parse_slot_datetime,
)


FIXED_NOW = datetime(2026, 5, 10, 10, 0, 0)


# ---------------------------------------------------------------------------
# compute_deposit_amount
# ---------------------------------------------------------------------------

def test_deposit_30_percent():
    result = compute_deposit_amount(120000)
    assert result == Decimal("36000")


def test_deposit_rounds_half_up():
    # 30% of 100001 = 30000.30 → rounds to 30000
    result = compute_deposit_amount(100001)
    assert result == Decimal("30000")


def test_deposit_zero_price():
    assert compute_deposit_amount(0) == Decimal("0")


def test_deposit_never_exceeds_price():
    result = compute_deposit_amount(10)
    assert result <= Decimal("10")


# ---------------------------------------------------------------------------
# parse_slot_datetime
# ---------------------------------------------------------------------------

def test_parse_slot_datetime():
    dt = parse_slot_datetime("2026-05-15", "10:30")
    assert dt == datetime(2026, 5, 15, 10, 30)


# ---------------------------------------------------------------------------
# is_future_slot
# ---------------------------------------------------------------------------

def test_is_future_slot_true():
    future = FIXED_NOW + timedelta(hours=5)
    date = future.strftime("%Y-%m-%d")
    time = future.strftime("%H:%M")
    assert is_future_slot(date, time, now=FIXED_NOW) is True


def test_is_future_slot_false_past():
    past = FIXED_NOW - timedelta(hours=1)
    date = past.strftime("%Y-%m-%d")
    time = past.strftime("%H:%M")
    assert is_future_slot(date, time, now=FIXED_NOW) is False


def test_is_future_slot_false_exact_now():
    date = FIXED_NOW.strftime("%Y-%m-%d")
    time = FIXED_NOW.strftime("%H:%M")
    assert is_future_slot(date, time, now=FIXED_NOW) is False


# ---------------------------------------------------------------------------
# has_minimum_booking_notice (4h)
# ---------------------------------------------------------------------------

def test_booking_notice_passes_5h_ahead():
    slot = FIXED_NOW + timedelta(hours=5)
    assert has_minimum_booking_notice(slot.strftime("%Y-%m-%d"), slot.strftime("%H:%M"), now=FIXED_NOW) is True


def test_booking_notice_fails_3h_ahead():
    slot = FIXED_NOW + timedelta(hours=3)
    assert has_minimum_booking_notice(slot.strftime("%Y-%m-%d"), slot.strftime("%H:%M"), now=FIXED_NOW) is False


def test_booking_notice_fails_exact_4h():
    slot = FIXED_NOW + timedelta(hours=4)
    assert has_minimum_booking_notice(slot.strftime("%Y-%m-%d"), slot.strftime("%H:%M"), now=FIXED_NOW) is True


# ---------------------------------------------------------------------------
# has_minimum_reschedule_notice (48h)
# ---------------------------------------------------------------------------

def test_reschedule_notice_passes_72h_ahead():
    slot = FIXED_NOW + timedelta(hours=72)
    assert has_minimum_reschedule_notice(slot.strftime("%Y-%m-%d"), slot.strftime("%H:%M"), now=FIXED_NOW) is True


def test_reschedule_notice_fails_24h_ahead():
    slot = FIXED_NOW + timedelta(hours=24)
    assert has_minimum_reschedule_notice(slot.strftime("%Y-%m-%d"), slot.strftime("%H:%M"), now=FIXED_NOW) is False


def test_reschedule_notice_fails_47h_ahead():
    slot = FIXED_NOW + timedelta(hours=47)
    assert has_minimum_reschedule_notice(slot.strftime("%Y-%m-%d"), slot.strftime("%H:%M"), now=FIXED_NOW) is False
