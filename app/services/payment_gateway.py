import hashlib
import json
from datetime import datetime
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.core.config import settings


WOMPI_FINAL_STATUSES = {
    "APPROVED": "approved",
    "DECLINED": "rejected",
    "ERROR": "rejected",
    "FAILED": "rejected",
    "VOIDED": "cancelled",
}


def is_wompi_enabled() -> bool:
    return settings.PAYMENT_PROVIDER.lower() == "wompi"


def is_wompi_fully_configured() -> bool:
    return bool(settings.WOMPI_PUBLIC_KEY and settings.WOMPI_INTEGRITY_SECRET)


def ensure_wompi_checkout_configured() -> None:
    if not is_wompi_fully_configured():
        raise HTTPException(status_code=503, detail="La pasarela Wompi no esta configurada")


def _to_utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    localized = value.replace(tzinfo=ZoneInfo(settings.BUSINESS_TIMEZONE))
    return localized.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _amount_in_cents(amount: Decimal | float | int) -> int:
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1")))


def build_wompi_checkout_data(payment, appointment) -> dict:
    ensure_wompi_checkout_configured()
    expiration_time = _to_utc_iso(appointment.payment_due_at)
    amount_in_cents = _amount_in_cents(payment.amount)
    signature_base = f"{payment.provider_reference}{amount_in_cents}{payment.currency}"
    if expiration_time:
        signature_base += expiration_time
    signature_base += settings.WOMPI_INTEGRITY_SECRET or ""

    redirect_url = (
        f"{settings.FRONTEND_APP_URL.rstrip('/')}/payments/checkout"
        f"?reference={quote(payment.provider_reference)}&stage=result"
    )
    return {
        "provider": "wompi",
        "public_key": settings.WOMPI_PUBLIC_KEY,
        "checkout_url": settings.WOMPI_CHECKOUT_URL,
        "amount_in_cents": amount_in_cents,
        "currency": payment.currency,
        "reference": payment.provider_reference,
        "integrity_signature": hashlib.sha256(signature_base.encode("utf-8")).hexdigest(),
        "redirect_url": redirect_url,
        "expiration_time": expiration_time,
        "customer_email": appointment.client_email,
        "customer_full_name": appointment.client_name,
        "customer_phone_number": appointment.client_phone,
    }


def get_checkout_payload(payment, appointment) -> tuple[str | None, dict | None]:
    provider = payment.provider.lower()
    if provider == "wompi":
        data = build_wompi_checkout_data(payment, appointment)
        return data["checkout_url"], data
    if provider == "mock":
        base = settings.PAYMENT_MOCK_CHECKOUT_BASE_URL.rstrip("/")
        return f"{base}/payments/checkout?reference={payment.provider_reference}", None
    return None, None


def map_wompi_transaction_status(status: str) -> str | None:
    normalized = (status or "").upper().strip()
    return WOMPI_FINAL_STATUSES.get(normalized)


def fetch_wompi_transaction(transaction_id: str) -> dict:
    if not settings.WOMPI_PUBLIC_KEY:
        raise HTTPException(status_code=503, detail="La llave publica de Wompi no esta configurada")

    request = Request(
        f"{settings.WOMPI_API_BASE_URL.rstrip('/')}/transactions/{quote(transaction_id)}",
        headers={"Authorization": f"Bearer {settings.WOMPI_PUBLIC_KEY}"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail="No fue posible consultar la transaccion en Wompi") from exc
    except URLError as exc:
        raise HTTPException(status_code=502, detail="Wompi no responde en este momento") from exc

    data = payload.get("data")
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Respuesta invalida de Wompi")
    return data


def verify_wompi_event_signature(payload: dict) -> bool:
    if not settings.WOMPI_EVENT_SECRET:
        return False

    signature = payload.get("signature") or {}
    properties = signature.get("properties") or []
    checksum = str(signature.get("checksum") or "").strip().lower()
    timestamp = str(payload.get("timestamp") or "").strip()
    data = payload.get("data") or {}
    if not properties or not checksum or not timestamp or not isinstance(data, dict):
        return False

    values: list[str] = []
    for path in properties:
        current = data
        for part in str(path).split("."):
            if not isinstance(current, dict) or part not in current:
                return False
            current = current[part]
        values.append(str(current))

    raw = "".join(values) + timestamp + settings.WOMPI_EVENT_SECRET
    expected = hashlib.sha256(raw.encode("utf-8")).hexdigest().lower()
    return expected == checksum
