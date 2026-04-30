from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.core.database import get_session
from app.services import workbench_service
from pydantic import BaseModel

router = APIRouter(prefix="/workbench", tags=["workbench"])

class AskRequest(BaseModel):
    datasource_id: int
    question: str

class ExecuteRequest(BaseModel):
    datasource_id: int
    sql: str

class ValidateRequest(BaseModel):
    sql: str

@router.post("/ask")
def ask(req: AskRequest, session: Session = Depends(get_session)):
    return workbench_service.ask_llm(session, req.datasource_id, req.question)

@router.post("/validate")
def validate(req: ValidateRequest):
    return workbench_service.validate_sql_candidate(req.sql)

@router.post("/execute")
def execute(req: ExecuteRequest, session: Session = Depends(get_session)):
    return workbench_service.execute_readonly_sql(session, req.datasource_id, req.sql)
