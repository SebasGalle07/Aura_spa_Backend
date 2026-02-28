from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.crud.service import get_service
from app.crud.professional import get_professional
from app.crud.appointment import list_appointments_by_professional_and_date

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


@router.get("", response_model=list[str])
def availability(service_id: int, professional_id: int, date: str, db: Session = Depends(get_db)):
    svc = get_service(db, service_id)
    pro = get_professional(db, professional_id)
    if not svc or not pro:
        raise HTTPException(status_code=404, detail="Service or professional not found")
    all_slots = gen_slots(pro.schedule_start, pro.schedule_end, svc.duration)
    apts = list_appointments_by_professional_and_date(db, professional_id, date)
    booked = {a.time for a in apts if a.status != "cancelled"}
    return [s for s in all_slots if s not in booked]
