import hashlib
import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
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

PAYU_FINAL_STATUSES = {
    "4": "approved",
    "6": "rejected",
    "104": "rejected",
    "5": "expired",
}


def _decimal_amount(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _amount_in_cents(amount: Decimal | float | int) -> int:
    return int((Decimal(str(amount)) * 100).quantize(Decimal("1")))


def _to_utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    localized = value.replace(tzinfo=ZoneInfo(settings.BUSINESS_TIMEZONE))
    return localized.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _payu_amount_variants(amount: Decimal | str | float | int) -> list[str]:
    decimal_amount = _decimal_amount(amount)
    return [
        f"{decimal_amount:.2f}",
        f"{decimal_amount:.1f}",
        str(decimal_amount.normalize()) if decimal_amount != decimal_amount.to_integral() else str(decimal_amount.quantize(Decimal('1'))),
    ]


def _hash_signature(base: str, algorithm: str) -> str:
    normalized = (algorithm or "MD5").upper().strip()
    if normalized in {"HMAC_SHA256", "HMAC-SHA256"}:
        return hashlib.sha256(base.encode("utf-8")).hexdigest()
    if normalized == "SHA256":
        return hashlib.sha256(base.encode("utf-8")).hexdigest()
    if normalized == "SHA1":
        return hashlib.sha1(base.encode("utf-8")).hexdigest()
    return hashlib.md5(base.encode("utf-8")).hexdigest()


def is_wompi_enabled() -> bool:
    return settings.PAYMENT_PROVIDER.lower() == "wompi"


def is_wompi_fully_configured() -> bool:
    return bool(settings.WOMPI_PUBLIC_KEY and settings.WOMPI_INTEGRITY_SECRET)


def ensure_wompi_checkout_configured() -> None:
    if not is_wompi_fully_configured():
        raise HTTPException(status_code=503, detail="La pasarela Wompi no esta configurada")


def is_payu_enabled() -> bool:
    return settings.PAYMENT_PROVIDER.lower() == "payu"


def is_payu_fully_configured() -> bool:
    return bool(settings.PAYU_MERCHANT_ID and settings.PAYU_ACCOUNT_ID and settings.PAYU_API_KEY)


def ensure_payu_checkout_configured() -> None:
    if not is_payu_fully_configured():
        raise HTTPException(status_code=503, detail="La pasarela PayU no esta configurada")


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
        f"?reference={quote(payment.provider_reference)}&provider=wompi&stage=result&returnTo=%2Fappointments"
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


def build_payu_checkout_data(payment, appointment) -> dict:
    ensure_payu_checkout_configured()
    amount = _decimal_amount(payment.amount)
    reference = payment.provider_reference
    signature_base = f"{settings.PAYU_API_KEY}~{settings.PAYU_MERCHANT_ID}~{reference}~{amount:.2f}~{payment.currency}"
    signature = _hash_signature(signature_base, settings.PAYU_SIGNATURE_ALGORITHM)
    description = f"Anticipo reserva Aura Spa #{appointment.id}"
    response_url = (
        f"{settings.FRONTEND_APP_URL.rstrip('/')}/payments/checkout"
        f"?reference={quote(reference)}&provider=payu&stage=result&returnTo=%2Fappointments"
    )
    confirmation_url = f"{settings.BACKEND_PUBLIC_URL.rstrip('/')}{settings.API_V1_STR}/appointments/payments/payu/confirmation"

    return {
        "provider": "payu",
        "checkout_url": settings.PAYU_CHECKOUT_URL,
        "merchant_id": settings.PAYU_MERCHANT_ID,
        "account_id": settings.PAYU_ACCOUNT_ID,
        "reference_code": reference,
        "description": description,
        "amount": f"{amount:.2f}",
        "currency": payment.currency,
        "tax": "0",
        "tax_return_base": "0",
        "signature": signature,
        "signature_algorithm": settings.PAYU_SIGNATURE_ALGORITHM,
        "test": "1" if settings.PAYU_ENV.lower() == "sandbox" else "0",
        "buyer_email": appointment.client_email,
        "response_url": response_url,
        "confirmation_url": confirmation_url,
        "payer_full_name": appointment.client_name,
        "mobile_phone": appointment.client_phone or "",
    }


def get_checkout_payload(payment, appointment) -> tuple[str | None, dict | None]:
    provider = payment.provider.lower()
    if provider == "payu":
        data = build_payu_checkout_data(payment, appointment)
        return data["checkout_url"], data
    if provider == "wompi":
        data = build_wompi_checkout_data(payment, appointment)
        return data["checkout_url"], data
    if provider == "mock":
        base = settings.PAYMENT_MOCK_CHECKOUT_BASE_URL.rstrip("/")
        return f"{base}/payments/checkout?reference={payment.provider_reference}", None
    return None, None


def map_payu_status(state_pol: str | None) -> str | None:
    return PAYU_FINAL_STATUSES.get(str(state_pol or "").strip())


def verify_payu_confirmation_signature(payload: dict) -> bool:
    if not settings.PAYU_API_KEY:
        return False
    provided_signature = str(payload.get("sign") or payload.get("signature") or "").strip().lower()
    merchant_id = str(payload.get("merchant_id") or payload.get("merchantId") or "").strip()
    reference_sale = str(payload.get("reference_sale") or payload.get("referenceCode") or "").strip()
    currency = str(payload.get("currency") or "").strip()
    state_pol = str(payload.get("state_pol") or payload.get("transactionState") or "").strip()
    raw_value = payload.get("value") or payload.get("TX_VALUE") or payload.get("amount")
    if not all([provided_signature, merchant_id, reference_sale, currency, state_pol, raw_value]):
        return False

    for amount_variant in _payu_amount_variants(raw_value):
        base = f"{settings.PAYU_API_KEY}~{merchant_id}~{reference_sale}~{amount_variant}~{currency}~{state_pol}"
        if _hash_signature(base, settings.PAYU_SIGNATURE_ALGORITHM).lower() == provided_signature:
            return True
        if hashlib.md5(base.encode("utf-8")).hexdigest().lower() == provided_signature:
            return True
    return False


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
