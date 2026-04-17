from datetime import datetime, timezone


def utc_now() -> datetime:
    """UTC sin timezone para mantener compatibilidad con columnas DateTime existentes."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_from_timestamp(timestamp: int | float) -> datetime:
    return datetime.fromtimestamp(timestamp, timezone.utc).replace(tzinfo=None)
