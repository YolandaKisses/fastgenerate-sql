from typing import Optional
import threading
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select
from app.core.database import engine, get_session
from app.models.datasource import DataSource
from app.models.knowledge import KnowledgeSyncTask
from app.models.schema import SchemaTable, SchemaField
from app.services import knowledge_service, schema_service
from pydantic import BaseModel

router = APIRouter(prefix="/schema", tags=["schema"])

class RemarkUpdate(BaseModel):
    remark: str

class KnowledgeTaskStatusResponse(BaseModel):
    task: Optional[KnowledgeSyncTask] = None
    actual_table_count: int = 0


def _is_pending_task(task: KnowledgeSyncTask) -> bool:
    status = getattr(task.status, "value", task.status)
    return status == "pending"

@router.post("/sync/{datasource_id}")
def sync_schema(datasource_id: int, session: Session = Depends(get_session)):
    ds = session.get(DataSource, datasource_id)
    if not ds:
        return {"success": False, "message": "DataSource not found"}
    return schema_service.sync_schema_for_datasource(session, ds)

@router.get("/tables/{datasource_id}", response_model=list[SchemaTable])
def read_tables(datasource_id: int, session: Session = Depends(get_session)):
    return schema_service.get_tables(session, datasource_id)

@router.patch("/tables/{table_id}/remark", response_model=SchemaTable)
def update_table_remark(table_id: int, remark_data: RemarkUpdate, session: Session = Depends(get_session)):
    return schema_service.update_table_remark(session, table_id, remark_data.remark)

@router.get("/fields/{table_id}", response_model=list[SchemaField])
def read_fields(table_id: int, session: Session = Depends(get_session)):
    return schema_service.get_fields(session, table_id)

@router.patch("/fields/{field_id}/remark", response_model=SchemaField)
def update_field_remark(field_id: int, remark_data: RemarkUpdate, session: Session = Depends(get_session)):
    return schema_service.update_field_remark(session, field_id, remark_data.remark)


@router.post("/knowledge/sync/{datasource_id}", response_model=KnowledgeSyncTask)
def start_knowledge_sync(
    datasource_id: int,
    session: Session = Depends(get_session),
):
    """启动后台知识库同步任务。刷新页面不会中断任务。"""
    try:
        task = knowledge_service.create_knowledge_sync_task(session, datasource_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if _is_pending_task(task):
        threading.Thread(
            target=knowledge_service.run_knowledge_sync_task,
            args=(engine, task.id),
            daemon=True,
        ).start()
    return task


@router.get("/knowledge/tasks/{task_id}/events")
def stream_knowledge_task_events(task_id: int):
    """SSE 订阅任务进度；只订阅，不执行任务。"""
    return StreamingResponse(
        knowledge_service.stream_knowledge_task_events(engine, task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/knowledge/sync_stream/{datasource_id}")
def sync_knowledge_stream(
    datasource_id: int,
    session: Session = Depends(get_session),
):
    """兼容旧入口：启动后台任务并用 SSE 订阅进度。"""
    try:
        task = knowledge_service.create_knowledge_sync_task(session, datasource_id)
    except ValueError as exc:
        # 无法创建任务时，仍返回 SSE 流以保持协议一致
        import json
        def _error_stream():
            yield f"event: error\ndata: {json.dumps({'message': str(exc)}, ensure_ascii=False)}\n\n"
        return StreamingResponse(
            _error_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    if _is_pending_task(task):
        threading.Thread(
            target=knowledge_service.run_knowledge_sync_task,
            args=(engine, task.id),
            daemon=True,
        ).start()

    return StreamingResponse(
        knowledge_service.run_knowledge_sync_stream(engine, task.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/knowledge/tasks/{task_id}", response_model=KnowledgeSyncTask)
def read_knowledge_task(task_id: int, session: Session = Depends(get_session)):
    task = session.get(KnowledgeSyncTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/knowledge/status/{datasource_id}", response_model=KnowledgeTaskStatusResponse)
def read_latest_knowledge_task(datasource_id: int, session: Session = Depends(get_session)):
    task = knowledge_service.get_latest_knowledge_sync_task(session, datasource_id)
    # 计算当前数据源下实际拥有的表数量
    from sqlalchemy import func
    actual_table_count = session.exec(
        select(func.count(SchemaTable.id)).where(SchemaTable.datasource_id == datasource_id)
    ).one()
    
    return {
        "task": task,
        "actual_table_count": actual_table_count
    }
