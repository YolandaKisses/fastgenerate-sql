from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.core.database import get_session
from app.services import workbench_service
from pydantic import BaseModel

router = APIRouter(prefix="/model-config", tags=["model-config"])

class ModelConfigUpdate(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    model_name: str | None = None
    timeout: int | None = None
    temperature: float | None = None

@router.get("/")
def get_config(session: Session = Depends(get_session)):
    config = workbench_service.get_or_create_config(session)
    return config

@router.put("/")
def save_config(data: ModelConfigUpdate, session: Session = Depends(get_session)):
    config = workbench_service.save_config(session, data.model_dump(exclude_unset=True))
    return config
