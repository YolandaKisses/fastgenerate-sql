from typing import Optional
import threading
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from app.api.deps import get_current_user, get_owned_datasource_or_404
from app.core.database import engine, get_session
from app.models.datasource import DataSource
from app.models.knowledge import KnowledgeSyncTask
from app.models.routine import RoutineDefinition
from app.models.view import ViewDefinition
from app.models.schema import SchemaTable, SchemaField
from app.services import knowledge_service, routine_service, schema_service, view_service
from pydantic import BaseModel

router = APIRouter(prefix="/schema", tags=["schema"], dependencies=[Depends(get_current_user)])

class RemarkUpdate(BaseModel):
    remark: str

class RelatedTablesUpdate(BaseModel):
    related_tables: str

class KnowledgeTaskStatusResponse(BaseModel):
    task: Optional[KnowledgeSyncTask] = None
    latest_datasource_task: Optional[KnowledgeSyncTask] = None
    actual_table_count: int = 0
    wiki_table_count: int = 0


class SyncRequest(BaseModel):
    mode: str = "basic"
    is_incremental: bool = False


def _is_pending_task(task: KnowledgeSyncTask) -> bool:
    status = getattr(task.status, "value", task.status)
    return status == "pending"

@router.post("/sync/{datasource_id}")
def sync_schema(datasource_id: int, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    ds = get_owned_datasource_or_404(session, datasource_id, current_user)
    return schema_service.sync_schema_for_datasource(session, ds)


@router.post("/routines/sync/{datasource_id}")
def sync_routines(datasource_id: int, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    ds = get_owned_datasource_or_404(session, datasource_id, current_user)
    return routine_service.sync_routines_for_datasource(session, ds)


@router.post("/views/sync/{datasource_id}")
def sync_views(datasource_id: int, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    ds = get_owned_datasource_or_404(session, datasource_id, current_user)
    return view_service.sync_views_for_datasource(session, ds)


@router.get("/routines/{datasource_id}", response_model=list[RoutineDefinition])
def read_routines(datasource_id: int, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    get_owned_datasource_or_404(session, datasource_id, current_user)
    return routine_service.get_routines(session, datasource_id)


@router.get("/views/{datasource_id}", response_model=list[ViewDefinition])
def read_views(datasource_id: int, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    get_owned_datasource_or_404(session, datasource_id, current_user)
    return view_service.get_views(session, datasource_id)

@router.get("/tables/{datasource_id}", response_model=list[SchemaTable])
def read_tables(datasource_id: int, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    get_owned_datasource_or_404(session, datasource_id, current_user)
    return schema_service.get_tables(session, datasource_id)

@router.patch("/tables/{table_id}/remark", response_model=SchemaTable)
def update_table_remark(table_id: int, remark_data: RemarkUpdate, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    table = session.get(SchemaTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    get_owned_datasource_or_404(session, table.datasource_id, current_user)
    return schema_service.update_table_remark(session, table_id, remark_data.remark)

@router.patch("/tables/{table_id}/related-tables", response_model=SchemaTable)
def update_table_related_tables(table_id: int, data: RelatedTablesUpdate, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    table = session.get(SchemaTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    get_owned_datasource_or_404(session, table.datasource_id, current_user)
    return schema_service.update_table_related_tables(session, table_id, data.related_tables)

@router.get("/fields/{table_id}", response_model=list[SchemaField])
def read_fields(table_id: int, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    table = session.get(SchemaTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    get_owned_datasource_or_404(session, table.datasource_id, current_user)
    return schema_service.get_fields(session, table_id)

@router.patch("/fields/{field_id}/remark", response_model=SchemaField)
def update_field_remark(field_id: int, remark_data: RemarkUpdate, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    field = session.get(SchemaField, field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    table = session.get(SchemaTable, field.table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    get_owned_datasource_or_404(session, table.datasource_id, current_user)
    return schema_service.update_field_remark(session, field_id, remark_data.remark)


@router.post("/knowledge/sync/{datasource_id}", response_model=KnowledgeSyncTask)
def start_knowledge_sync(
    datasource_id: int,
    request_data: SyncRequest,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """启动数据源级后台知识库同步任务。"""
    from app.models.knowledge import KnowledgeSyncScope

    get_owned_datasource_or_404(session, datasource_id, current_user)

    mode = knowledge_service.validate_sync_mode(request_data.mode)
    task = knowledge_service.create_knowledge_sync_task(
        session, 
        datasource_id, 
        scope=KnowledgeSyncScope.DATASOURCE,
        mode=mode,
        is_incremental=request_data.is_incremental
    )

    if _is_pending_task(task):
        threading.Thread(
            target=knowledge_service.run_knowledge_sync_task,
            args=(engine, task.id),
            daemon=True,
        ).start()
    return task


@router.post("/knowledge/sync-table/{table_id}", response_model=KnowledgeSyncTask)
def start_table_knowledge_sync(
    table_id: int,
    request_data: SyncRequest,
    session: Session = Depends(get_session),
    current_user = Depends(get_current_user)
):
    """启动单表后台知识库同步任务。"""
    from app.models.knowledge import KnowledgeSyncScope

    table = session.get(SchemaTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    get_owned_datasource_or_404(session, table.datasource_id, current_user)
        
    mode = knowledge_service.validate_sync_mode(request_data.mode)
    task = knowledge_service.create_knowledge_sync_task(
        session, 
        table.datasource_id, 
        scope=KnowledgeSyncScope.TABLE,
        mode=mode,
        target_table_id=table_id
    )

    if _is_pending_task(task):
        threading.Thread(
            target=knowledge_service.run_knowledge_sync_task,
            args=(engine, task.id),
            daemon=True,
        ).start()
    return task


@router.get("/knowledge/tasks/{task_id}/events")
def stream_knowledge_task_events(task_id: int, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    """SSE 订阅任务进度；只订阅，不执行任务。"""
    task = session.get(KnowledgeSyncTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    get_owned_datasource_or_404(session, task.datasource_id, current_user)

    return StreamingResponse(
        knowledge_service.stream_knowledge_task_events(engine, task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/knowledge/tasks/{task_id}", response_model=KnowledgeSyncTask)
def read_knowledge_task(task_id: int, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    task = session.get(KnowledgeSyncTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    get_owned_datasource_or_404(session, task.datasource_id, current_user)
    return task


@router.post("/knowledge/tasks/{task_id}/stop")
def stop_knowledge_task(task_id: int, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    task = session.get(KnowledgeSyncTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    get_owned_datasource_or_404(session, task.datasource_id, current_user)
    
    success = knowledge_service.stop_knowledge_sync_task(engine, task_id)
    return {"success": success}


@router.get("/knowledge/status/{datasource_id}", response_model=KnowledgeTaskStatusResponse)
def read_latest_knowledge_task(datasource_id: int, session: Session = Depends(get_session), current_user = Depends(get_current_user)):
    ds = get_owned_datasource_or_404(session, datasource_id, current_user)
    task = knowledge_service.get_latest_knowledge_sync_task(session, datasource_id)
    latest_ds_task = knowledge_service.get_latest_knowledge_sync_task(
        session, datasource_id, scope="datasource"
    )
    # 计算当前数据源下实际拥有的表数量
    from sqlalchemy import func
    actual_table_count = session.exec(
        select(func.count(SchemaTable.id)).where(SchemaTable.datasource_id == datasource_id)
    ).one()

    from pathlib import Path
    from app.core.config import settings
    from app.services.path_utils import sanitize_path_segment

    from app.services import setting_service
    vault_root = setting_service.get_setting(session, "wiki_root", settings.WIKI_ROOT)
    wiki_tables_dir = Path(vault_root) / sanitize_path_segment(ds.name) / "tables"
    wiki_table_count = 0
    if wiki_tables_dir.exists():
        wiki_table_count = len(list(wiki_tables_dir.glob("*.md")))
    
    return {
        "task": task,
        "latest_datasource_task": latest_ds_task,
        "actual_table_count": actual_table_count,
        "wiki_table_count": wiki_table_count,
    }
