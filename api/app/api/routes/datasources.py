from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlmodel import Session
from app.api.deps import get_current_user, get_owned_datasource_or_404
from app.core.database import get_session
from app.models.datasource import DataSourceCreate, DataSourceRead, DataSourceStatus, DataSourceUpdate, SourceMode, SourceStatus
from app.services import datasource_service, sql_import_service

router = APIRouter(prefix="/datasources", tags=["datasources"], dependencies=[Depends(get_current_user)])

@router.post("/", response_model=DataSourceRead)
async def create_datasource(request: Request, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    content_type = request.headers.get("content-type", "")
    if (
        content_type.startswith("multipart/form-data")
        or content_type.startswith("application/x-www-form-urlencoded")
    ):
        form = await request.form()
        payload = {
            "name": form.get("name"),
            "db_type": form.get("db_type"),
            "host": form.get("host"),
            "port": int(form["port"]) if form.get("port") else None,
            "database": form.get("database"),
            "username": form.get("username"),
            "password": form.get("password"),
            "auth_type": form.get("auth_type") or "password",
            "source_mode": form.get("source_mode") or SourceMode.CONNECTION,
        }
        ds_in = DataSourceCreate.model_validate(payload)
        datasource = datasource_service.create_datasource(session, ds_in, current_user.user_id)
        if datasource.source_mode == SourceMode.SQL_FILE:
            files = [
                value
                for _key, value in form.multi_items()
                if hasattr(value, "filename") and hasattr(value, "read")
            ]
            if not files:
                raise HTTPException(status_code=400, detail="SQL 文件模式必须上传至少一个 .sql 文件")
            return await sql_import_service.create_sql_import_batch(session, datasource, files)
        return datasource

    payload = await request.json()
    ds_in = DataSourceCreate.model_validate(payload)
    if ds_in.source_mode == SourceMode.SQL_FILE:
        raise HTTPException(
            status_code=400,
            detail="SQL 文件模式创建必须使用 multipart/form-data 并上传 .sql 文件",
        )
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

@router.post("/{ds_id}/test", response_model=dict)
async def test_datasource(ds_id: int, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    ds = get_owned_datasource_or_404(session, ds_id, current_user)
    
    # 将同步的测试连接操作放入线程池执行，防止超时阻塞主事件循环
    res = await run_in_threadpool(datasource_service.test_connection, ds)
    if res["success"]:
        ds.status = DataSourceStatus.CONNECTION_OK
        ds.source_status = SourceStatus.CONNECTION_OK
    else:
        ds.status = DataSourceStatus.CONNECTION_FAILED
        ds.source_message = res.get("message")
    
    session.add(ds)
    session.commit()
    return res


@router.post("/{ds_id}/upload-sql", response_model=DataSourceRead)
async def upload_sql_files(
    ds_id: int,
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user),
):
    ds = get_owned_datasource_or_404(session, ds_id, current_user)
    return await sql_import_service.create_sql_import_batch(session, ds, files)


@router.post("/{ds_id}/parse-sql", response_model=dict)
def parse_sql_files(
    ds_id: int,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user),
):
    ds = get_owned_datasource_or_404(session, ds_id, current_user)
    return sql_import_service.parse_latest_sql_import_batch(session, ds)
