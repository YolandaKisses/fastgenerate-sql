from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.api.deps import get_current_user
from app.core.database import get_session
from app.models.audit_log import AuditLog
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

router = APIRouter(prefix="/audit", tags=["audit"], dependencies=[Depends(get_current_user)])

@router.get("/logs")
def get_logs(session: Session = Depends(get_session)):
    logs = session.exec(select(AuditLog).order_by(AuditLog.created_at.desc())).all()
    return logs

@router.delete("/logs/{log_id}")
def delete_log(log_id: int, session: Session = Depends(get_session)):
    log = session.get(AuditLog, log_id)
    if not log:
        return {"success": False, "message": "日志不存在"}
    session.delete(log)
    session.commit()
    return {"success": True}
