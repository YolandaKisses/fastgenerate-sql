from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.core.database import get_session
from app.models.datasource import DataSource, DataSourceCreate, DataSourceRead, DataSourceUpdate, DataSourceStatus
from app.services import datasource_service

router = APIRouter(prefix="/datasources", tags=["datasources"])

@router.post("/", response_model=DataSourceRead)
def create_datasource(ds_in: DataSourceCreate, session: Session = Depends(get_session)):
    return datasource_service.create_datasource(session, ds_in)

@router.get("/", response_model=list[DataSourceRead])
def read_datasources(session: Session = Depends(get_session)):
    return datasource_service.get_datasources(session)

@router.patch("/{ds_id}", response_model=DataSourceRead)
def update_datasource(ds_id: int, ds_in: DataSourceUpdate, session: Session = Depends(get_session)):
    return datasource_service.update_datasource(session, ds_id, ds_in)

@router.post("/{ds_id}/test", response_model=dict)
def test_datasource(ds_id: int, session: Session = Depends(get_session)):
    ds = session.get(DataSource, ds_id)
    if not ds:
        return {"success": False, "message": "DataSource not found"}
    
    res = datasource_service.test_connection(ds)
    if res["success"]:
        ds.status = DataSourceStatus.CONNECTION_OK
    else:
        ds.status = DataSourceStatus.CONNECTION_FAILED
    
    session.add(ds)
    session.commit()
    return res
