from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.specialty_match import is_professional_compatible_with_service
from app.db.deps import get_db
from app.crud.service import get_service
from app.crud.professional import get_professional
from app.crud.appointment import is_slot_blocked, list_appointments_by_professional_and_date_with_duration
from app.services.reservation_workflow import expire_pending_appointments

router = APIRouter()


def gen_slots(start: str, end: str, duration: int) -> list[str]:
    slots = []
    sh, sm = [int(x) for x in start.split(":")]
    eh, em = [int(x) for x in end.split(":")]
    end_min = eh * 60 + em
    while sh * 60 + sm + duration <= end_min:
        slots.append(f"{sh:02d}:{sm:02d}")
        sm += duration
        if sm >= 60:
            sh += sm // 60
            sm = sm % 60
    return slots


def _to_minutes(time_str: str) -> int:
    h, m = [int(x) for x in time_str.split(":")]
    return h * 60 + m


@router.get("", response_model=list[str])
def availability(service_id: int, professional_id: int, date: str, db: Session = Depends(get_db)):
    expire_pending_appointments(db, commit=True)

    svc = get_service(db, service_id)
    pro = get_professional(db, professional_id)
    if not svc or not pro:
        raise HTTPException(status_code=404, detail="Service or professional not found")
    if not is_professional_compatible_with_service(svc.category, pro.specialty):
        return []

    all_slots = gen_slots(pro.schedule_start, pro.schedule_end, svc.duration)
    apts = list_appointments_by_professional_and_date_with_duration(db, professional_id, date)
    available = []
    for slot in all_slots:
        start = _to_minutes(slot)
        end = start + svc.duration
        overlap = False
        for apt, apt_duration in apts:
            if not is_slot_blocked(apt):
                continue
            apt_start = _to_minutes(apt.time)
            apt_end = apt_start + (apt_duration or svc.duration)
            if start < apt_end and apt_start < end:
                overlap = True
                break
        if not overlap:
            available.append(slot)
    return available
