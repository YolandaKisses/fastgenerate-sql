from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.database import get_session
from app.models.datasource import DataSource
from app.services import lineage_service

router = APIRouter(prefix="/lineage", tags=["lineage"], dependencies=[Depends(get_current_user)])


def _ensure_datasource(session: Session, datasource_id: int, user_id: str) -> DataSource:
    ds = session.get(DataSource, datasource_id)
    if not ds or ds.user_id != user_id:
        raise HTTPException(status_code=404, detail="DataSource not found")
    return ds


@router.get("/table/{datasource_id}/{table_name}")
def read_table_lineage(
    datasource_id: int,
    table_name: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    _ensure_datasource(session, datasource_id, current_user.user_id)
    try:
        return lineage_service.get_table_lineage(
            session,
            datasource_id=datasource_id,
            table_name=table_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/routine/{datasource_id}/{routine_name}")
def read_routine_lineage(
    datasource_id: int,
    routine_name: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    _ensure_datasource(session, datasource_id, current_user.user_id)
    try:
        return lineage_service.get_routine_lineage(
            session,
            datasource_id=datasource_id,
            routine_name=routine_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/view/{datasource_id}/{view_name}")
def read_view_lineage(
    datasource_id: int,
    view_name: str,
    session: Session = Depends(get_session),
    current_user=Depends(get_current_user),
):
    _ensure_datasource(session, datasource_id, current_user.user_id)
    try:
        return lineage_service.get_view_lineage(
            session,
            datasource_id=datasource_id,
            view_name=view_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
