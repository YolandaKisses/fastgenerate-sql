from __future__ import annotations

import json
import re
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.database import get_session
from app.services.hermes_service import list_hermes_sessions, get_hermes_session_messages
from app.services.workbench_service import ask_llm, ask_llm_stream


SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
router = APIRouter(prefix="/workbench", tags=["workbench"], dependencies=[Depends(get_current_user)])


def is_valid_hermes_session_id(value: str) -> bool:
    if not value or len(value) > 128:
        return False
    if ".." in value or "/" in value or "\\" in value or " " in value:
        return False
    return SESSION_ID_PATTERN.match(value) is not None


def _parse_history(raw: str | None) -> list[dict[str, str]]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="history 不是合法 JSON") from exc
    if not isinstance(value, list):
        raise HTTPException(status_code=400, detail="history 必须是数组")
    history: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()
        if role and content:
            history.append({"role": role, "content": content})
    return history


@router.post("/ask")
def workbench_ask(
    datasource_id: int,
    question: str,
    history: str | None = None,
    hermes_session_id: str | None = None,
    session: Session = Depends(get_session),
):
    if hermes_session_id and not is_valid_hermes_session_id(hermes_session_id):
        raise HTTPException(status_code=400, detail="非法的 Hermes session_id")
    return ask_llm(
        session,
        datasource_id,
        question,
        history=_parse_history(history),
        hermes_session_id=hermes_session_id,
    )


@router.get("/ask_stream")
def workbench_ask_stream(
    datasource_id: int = Query(...),
    question: str = Query(..., min_length=1),
    history: str | None = Query(default=None),
    hermes_session_id: str | None = Query(default=None),
    session: Session = Depends(get_session),
):
    if hermes_session_id and not is_valid_hermes_session_id(hermes_session_id):
        raise HTTPException(status_code=400, detail="非法的 Hermes session_id")
    return StreamingResponse(
        ask_llm_stream(
            session,
            datasource_id,
            question,
            history=_parse_history(history),
            hermes_session_id=hermes_session_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions")
def workbench_sessions():
    return {"items": list_hermes_sessions()}


@router.get("/sessions/{session_id}")
def workbench_session_detail(session_id: str):
    if not is_valid_hermes_session_id(session_id):
        raise HTTPException(status_code=400, detail="非法的 Hermes session_id")
    return {"messages": get_hermes_session_messages(session_id)}
