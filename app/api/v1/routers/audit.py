from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_roles
from app.crud.audit import list_audit_logs
from app.db.deps import get_db
from app.schemas.audit import AuditLogOut

router = APIRouter()


@router.get("", response_model=list[AuditLogOut], dependencies=[Depends(require_roles("admin"))])
def get_audit_logs(limit: int = 100, offset: int = 0, db: Session = Depends(get_db)):
    return list_audit_logs(db, limit=limit, offset=offset)
