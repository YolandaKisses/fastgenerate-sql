from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session
from app.api.deps import get_current_user
from app.core.database import get_session
from app.services import workbench_service
from pydantic import BaseModel

router = APIRouter(prefix="/workbench", tags=["workbench"], dependencies=[Depends(get_current_user)])

import json
import re
from typing import List, Optional

HERMES_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def is_valid_hermes_session_id(session_id: str) -> bool:
    return bool(HERMES_SESSION_ID_RE.fullmatch(session_id))


def validate_optional_hermes_session_id(session_id: Optional[str]) -> None:
    if session_id is not None and not is_valid_hermes_session_id(session_id):
        raise HTTPException(status_code=400, detail="无效的 session_id 格式")

class AskRequest(BaseModel):
    datasource_id: int
    question: str
    history: Optional[List[dict]] = None
    hermes_session_id: Optional[str] = None

class ExecuteRequest(BaseModel):
    datasource_id: int
    sql: str
    audit_log_id: Optional[int] = None

class ValidateRequest(BaseModel):
    sql: str

@router.post("/ask")
def ask(req: AskRequest, session: Session = Depends(get_session)):
    validate_optional_hermes_session_id(req.hermes_session_id)
    return workbench_service.ask_llm(
        session,
        req.datasource_id,
        req.question,
        req.history,
        req.hermes_session_id,
    )


@router.get("/ask_stream")
def ask_stream(
    datasource_id: int = Query(...),
    question: str = Query(...),
    history: Optional[str] = Query(None),
    hermes_session_id: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """SSE 流式问答：实时推送 Hermes 调用过程"""
    validate_optional_hermes_session_id(hermes_session_id)

    # 解析 history JSON 字符串
    parsed_history = None
    if history:
        try:
            parsed_history = json.loads(history)
        except:
            pass

    return StreamingResponse(
        workbench_service.ask_llm_stream(
            session,
            datasource_id,
            question,
            parsed_history,
            hermes_session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/validate")
def validate(req: ValidateRequest):
    return workbench_service.validate_sql_candidate(req.sql)

@router.post("/execute")
def execute(req: ExecuteRequest, session: Session = Depends(get_session)):
    return workbench_service.execute_readonly_sql(session, req.datasource_id, req.sql, req.audit_log_id)
