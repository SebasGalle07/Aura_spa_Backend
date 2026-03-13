from __future__ import annotations

import logging
from threading import Event, Thread

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.reservation_workflow import expire_pending_appointments

logger = logging.getLogger(__name__)

_worker_thread: Thread | None = None
_stop_event = Event()


def _worker_loop():
    interval = max(5, int(settings.RESERVATION_EXPIRER_INTERVAL_SECONDS))
    while not _stop_event.wait(interval):
        db = SessionLocal()
        try:
            expired_count = expire_pending_appointments(db, commit=True)
            if expired_count:
                logger.info("Expired %s pending appointments", expired_count)
        except Exception:
            db.rollback()
            logger.exception("Failed while expiring pending appointments")
        finally:
            db.close()


def start_reservation_expirer():
    global _worker_thread
    if not settings.RESERVATION_EXPIRER_ENABLED:
        return
    if _worker_thread and _worker_thread.is_alive():
        return
    _stop_event.clear()
    _worker_thread = Thread(target=_worker_loop, name="reservation-expirer", daemon=True)
    _worker_thread.start()


def stop_reservation_expirer():
    _stop_event.set()
