from fastapi import APIRouter, Depends
from sqlmodel import Session
from app.api.deps import get_current_user
from app.core.database import get_session
from app.models.datasource import DataSource, DataSourceCreate, DataSourceRead, DataSourceUpdate, DataSourceStatus
from app.services import datasource_service

router = APIRouter(prefix="/datasources", tags=["datasources"], dependencies=[Depends(get_current_user)])

@router.post("/", response_model=DataSourceRead)
def create_datasource(ds_in: DataSourceCreate, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    return datasource_service.create_datasource(session, ds_in, current_user.user_id)

@router.get("/", response_model=list[DataSourceRead])
def read_datasources(session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    return datasource_service.get_datasources(session, current_user.user_id)

@router.patch("/{ds_id}", response_model=DataSourceRead)
def update_datasource(ds_id: int, ds_in: DataSourceUpdate, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    return datasource_service.update_datasource(session, ds_id, ds_in, current_user.user_id)

@router.delete("/{ds_id}", response_model=dict)
def delete_datasource(ds_id: int, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    return datasource_service.delete_datasource(session, ds_id, current_user.user_id)

from fastapi.concurrency import run_in_threadpool

@router.post("/{ds_id}/test", response_model=dict)
async def test_datasource(ds_id: int, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    ds = session.get(DataSource, ds_id)
    if not ds or ds.user_id != current_user.user_id:
        return {"success": False, "message": "DataSource not found"}
    
    # 将同步的测试连接操作放入线程池执行，防止超时阻塞主事件循环
    res = await run_in_threadpool(datasource_service.test_connection, ds)
    if res["success"]:
        ds.status = DataSourceStatus.CONNECTION_OK
    else:
        ds.status = DataSourceStatus.CONNECTION_FAILED
    
    session.add(ds)
    session.commit()
    return res
