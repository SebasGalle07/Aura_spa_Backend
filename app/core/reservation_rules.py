from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from app.core.config import settings

APPOINTMENT_PENDING_PAYMENT = "pending_payment"
APPOINTMENT_CONFIRMED = "confirmed"
APPOINTMENT_EXPIRED = "expired"
APPOINTMENT_CANCELLED = "cancelled"
APPOINTMENT_RESCHEDULED = "rescheduled"
APPOINTMENT_COMPLETED = "completed"
APPOINTMENT_NO_SHOW = "no_show"

PAYMENT_PENDING = "pending"
PAYMENT_APPROVED = "approved"
PAYMENT_REJECTED = "rejected"
PAYMENT_EXPIRED = "expired"
PAYMENT_CANCELLED = "cancelled"
PAYMENT_VOIDED = "voided"

ACTIVE_BLOCKING_STATUSES = {APPOINTMENT_PENDING_PAYMENT, APPOINTMENT_CONFIRMED, APPOINTMENT_RESCHEDULED}
FINAL_NON_BLOCKING_STATUSES = {APPOINTMENT_EXPIRED, APPOINTMENT_CANCELLED, APPOINTMENT_COMPLETED, APPOINTMENT_NO_SHOW}
PAYABLE_RESERVATION_STATUSES = {APPOINTMENT_PENDING_PAYMENT}
CANCELLABLE_STATUSES = {APPOINTMENT_PENDING_PAYMENT, APPOINTMENT_CONFIRMED, APPOINTMENT_RESCHEDULED}
REPROGRAMMABLE_STATUSES = {APPOINTMENT_CONFIRMED, APPOINTMENT_RESCHEDULED}
COMPLETABLE_STATUSES = {APPOINTMENT_CONFIRMED, APPOINTMENT_RESCHEDULED}
TERMINAL_PAYMENT_STATUSES = {PAYMENT_APPROVED, PAYMENT_REJECTED, PAYMENT_EXPIRED, PAYMENT_CANCELLED, PAYMENT_VOIDED}


def compute_deposit_amount(service_price: int) -> Decimal:
    if settings.RESERVATION_DEPOSIT_FIXED > 0:
        amount = Decimal(str(settings.RESERVATION_DEPOSIT_FIXED))
    else:
        percent = Decimal(str(settings.RESERVATION_DEPOSIT_PERCENT)) / Decimal("100")
        amount = (Decimal(str(service_price)) * percent).quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    if amount < 0:
        amount = Decimal("0")
    if amount > Decimal(str(service_price)):
        amount = Decimal(str(service_price))
    return amount


def current_business_datetime(now: datetime | None = None) -> datetime:
    if now is not None:
        return now
    timezone = ZoneInfo(settings.BUSINESS_TIMEZONE)
    return datetime.now(timezone).replace(tzinfo=None)


def compute_payment_due_at(now: datetime | None = None) -> datetime:
    base = current_business_datetime(now)
    return base + timedelta(minutes=settings.RESERVATION_HOLD_MINUTES)


def parse_slot_datetime(date: str, time: str) -> datetime:
    return datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")


def is_future_slot(date: str, time: str, now: datetime | None = None) -> bool:
    return parse_slot_datetime(date, time) > current_business_datetime(now)


def has_minimum_booking_notice(date: str, time: str, now: datetime | None = None) -> bool:
    base = current_business_datetime(now)
    scheduled_at = parse_slot_datetime(date, time)
    return (scheduled_at - base) >= timedelta(hours=settings.RESERVATION_MIN_LEAD_HOURS)


def has_minimum_reschedule_notice(date: str, time: str, now: datetime | None = None) -> bool:
    base = current_business_datetime(now)
    scheduled_at = parse_slot_datetime(date, time)
    return (scheduled_at - base) >= timedelta(hours=settings.RESCHEDULE_MIN_HOURS)
