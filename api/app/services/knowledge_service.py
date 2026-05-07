from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import re
from typing import Generator
import threading

import sqlalchemy
from sqlmodel import Session, select

from app.core.config import settings
from app.models.datasource import DataSource, DataSourceStatus, SyncStatus
from app.models.knowledge import (
    KnowledgeSyncTask, 
    KnowledgeSyncTaskStatus,
    KnowledgeSyncScope,
    KnowledgeSyncMode
)
from app.models.schema import SchemaField, SchemaTable
from app.services.hermes_service import run_hermes_json
from app.services import setting_service
from app.services.path_utils import sanitize_path_segment

STALE_RUNNING_TASK_AFTER = timedelta(minutes=8)


class _TaskNotifier:
    """In-process task update notifier with per-subscriber version tracking."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._channels: dict[int, tuple[threading.Condition, list[int]]] = {}

    def _ensure(self, task_id: int) -> tuple[threading.Condition, list[int]]:
        with self._lock:
            if task_id not in self._channels:
                self._channels[task_id] = (threading.Condition(), [0])
            return self._channels[task_id]

    def notify(self, task_id: int) -> None:
        condition, version = self._ensure(task_id)
        with condition:
            version[0] += 1
            condition.notify_all()

    def wait(self, task_id: int, last_version: int, timeout: float = 5.0) -> int:
        condition, version = self._ensure(task_id)
        with condition:
            condition.wait_for(lambda: version[0] > last_version, timeout=timeout)
            return version[0]

    def cleanup(self, task_id: int) -> None:
        with self._lock:
            self._channels.pop(task_id, None)


_notifier = _TaskNotifier()


def _notify_task_updated(task_id: int | None) -> None:
    if task_id is not None:
        _notifier.notify(task_id)


def _is_missing_knowledge_task_column_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "no such column" in message
        and "knowledgesynctask." in message
    )


def get_obsidian_root_path(session: Session) -> str:
    return setting_service.get_setting(session, "obsidian_vault_root", settings.OBSIDIAN_VAULT_ROOT)


def validate_sync_mode(mode: str) -> KnowledgeSyncMode:
    try:
        return KnowledgeSyncMode(mode)
    except ValueError as exc:
        raise ValueError(f"不支持的同步模式: {mode}") from exc


def reuse_or_reject_active_task(
    active_task: KnowledgeSyncTask | None,
    *,
    scope: KnowledgeSyncScope,
    mode: KnowledgeSyncMode,
    target_table_id: int | None,
) -> KnowledgeSyncTask | None:
    if not active_task:
        return None

    active_scope = KnowledgeSyncScope(getattr(active_task, "scope", KnowledgeSyncScope.DATASOURCE))
    active_mode = KnowledgeSyncMode(getattr(active_task, "mode", KnowledgeSyncMode.BASIC))
    active_target_table_id = getattr(active_task, "target_table_id", None)

    if (
        active_scope == scope
        and active_mode == mode
        and active_target_table_id == target_table_id
    ):
        return active_task

    raise ValueError("当前数据源已有知识库同步任务进行中，请稍后再试")


def create_knowledge_sync_task(
    session: Session, 
    datasource_id: int, 
    scope: KnowledgeSyncScope = KnowledgeSyncScope.DATASOURCE,
    mode: KnowledgeSyncMode = KnowledgeSyncMode.BASIC,
    target_table_id: int | None = None
) -> KnowledgeSyncTask:
    mark_stale_knowledge_sync_tasks(session, datasource_id=datasource_id)

    active_task = reuse_or_reject_active_task(
        get_active_knowledge_sync_task(session, datasource_id),
        scope=scope,
        mode=mode,
        target_table_id=target_table_id,
    )
    if active_task:
        return active_task

    datasource = session.get(DataSource, datasource_id)
    if not datasource:
        raise ValueError("数据源不存在")

    target_table_name = None
    if scope == KnowledgeSyncScope.TABLE:
        if not target_table_id:
            raise ValueError("单表同步必须提供 table_id")
        table = session.get(SchemaTable, target_table_id)
        if not table:
            raise ValueError("目标表不存在")
        target_table_name = table.name
        total_tables = 1
    else:
        tables = session.exec(
            select(SchemaTable).where(SchemaTable.datasource_id == datasource_id)
        ).all()
        if not tables:
            raise ValueError("未找到已同步表，无法同步到知识库")
        total_tables = len(tables)

    output_root = get_obsidian_root_path(session)
    output_dir = str(Path(output_root) / sanitize_path_segment(datasource.name))
    task = KnowledgeSyncTask(
        datasource_id=datasource.id,
        datasource_name=datasource.name,
        scope=scope,
        mode=mode,
        target_table_id=target_table_id,
        target_table_name=target_table_name,
        total_tables=total_tables,
        output_root=output_root,
        output_dir=output_dir,
    )
    session.add(task)
    datasource.status = DataSourceStatus.CONNECTION_OK
    datasource.sync_status = SyncStatus.SYNCING
    datasource.last_sync_message = f"知识库同步任务({scope}/{mode})已创建"
    session.add(datasource)
    session.commit()
    session.refresh(task)
    _notify_task_updated(task.id)
    return task


def get_active_knowledge_sync_task(session: Session, datasource_id: int) -> KnowledgeSyncTask | None:
    statement = (
        select(KnowledgeSyncTask)
        .where(
            KnowledgeSyncTask.datasource_id == datasource_id,
            KnowledgeSyncTask.status.in_([
                KnowledgeSyncTaskStatus.PENDING,
                KnowledgeSyncTaskStatus.RUNNING,
            ]),
        )
        .order_by(KnowledgeSyncTask.id.desc())
        .limit(1)
    )
    try:
        return session.exec(statement).first()
    except sqlalchemy.exc.OperationalError as exc:
        if _is_missing_knowledge_task_column_error(exc):
            return None
        raise


def get_latest_knowledge_sync_task(session: Session, datasource_id: int, scope: str = None) -> KnowledgeSyncTask | None:
    mark_stale_knowledge_sync_tasks(session, datasource_id=datasource_id)

    statement = (
        select(KnowledgeSyncTask)
        .where(KnowledgeSyncTask.datasource_id == datasource_id)
    )
    if scope:
        statement = statement.where(KnowledgeSyncTask.scope == scope)
    
    statement = statement.order_by(KnowledgeSyncTask.id.desc()).limit(1)
    try:
        return session.exec(statement).first()
    except sqlalchemy.exc.OperationalError as exc:
        if _is_missing_knowledge_task_column_error(exc):
            return None
        raise


def mark_stale_knowledge_sync_tasks(
    session: Session,
    datasource_id: int | None = None,
    now: datetime | None = None,
) -> int:
    now = now or datetime.now()
    stale_before = now - STALE_RUNNING_TASK_AFTER
    running_statuses = [
        KnowledgeSyncTaskStatus.PENDING,
        KnowledgeSyncTaskStatus.RUNNING,
    ]
    statement = select(KnowledgeSyncTask).where(KnowledgeSyncTask.status.in_(running_statuses))
    if datasource_id is not None:
        statement = statement.where(KnowledgeSyncTask.datasource_id == datasource_id)

    stale_tasks = []
    try:
        running_tasks = session.exec(statement).all()
    except sqlalchemy.exc.OperationalError as exc:
        if _is_missing_knowledge_task_column_error(exc):
            return 0
        raise

    for task in running_tasks:
        reference_time = task.updated_at or task.started_at or task.created_at
        if reference_time and reference_time < stale_before:
            stale_tasks.append(task)

    for task in stale_tasks:
        task.status = KnowledgeSyncTaskStatus.FAILED
        task.error_message = "知识库同步任务已超时或连接中断，请重新同步"
        task.current_phase = "failed"
        task.last_message = task.error_message
        task.finished_at = now
        session.add(task)

    if stale_tasks:
        session.commit()
        for task in stale_tasks:
            _notify_task_updated(task.id)

    return len(stale_tasks)


def update_knowledge_task_progress(
    session: Session,
    task: KnowledgeSyncTask,
    phase: str,
    message: str,
    current_table: str | None = None,
) -> None:
    task.current_phase = phase
    task.last_message = message
    task.current_table = current_table
    task.updated_at = datetime.now()
    session.add(task)
    session.commit()
    _notify_task_updated(task.id)


def knowledge_task_payload(task: KnowledgeSyncTask) -> dict:
    return {
        "task_id": task.id,
        "status": task.status.value if isinstance(task.status, KnowledgeSyncTaskStatus) else task.status,
        "scope": task.scope,
        "mode": task.mode,
        "phase": task.current_phase,
        "message": task.last_message,
        "completed_tables": task.completed_tables,
        "failed_tables": task.failed_tables,
        "total_tables": task.total_tables,
        "current_table": task.current_table,
        "error_message": task.error_message,
    }


def render_table_markdown(
    datasource: DataSource,
    table: SchemaTable,
    fields: list[SchemaField],
    summary: dict[str, str],
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now()
    note_properties = build_note_properties(datasource, table, summary, generated_at)
    frontmatter = render_frontmatter(note_properties)
    graph_links = summary.get("graph_links") or []
    relationships = summary.get("relationships")
    core_fields = summary.get("core_fields")

    # --- 概述（合并：基础信息 + 用途说明） ---
    lines = [
        frontmatter,
        "",
        f"# {table.name}",
        "",
        "[[../index|返回数据源总览]]",
        "",
        "## 概述",
        f"- **数据源**: {datasource.name}",
        f"- **业务说明**: {summary.get('purpose', '暂无')}",
    ]

    # --- 表间关系（合并：关联表 + 关联笔记 + 常见关联关系） ---
    lines.extend(["", "## 表间关系"])
    has_relationship_content = False

    # 用户配置的关联关系
    if relationships:
        lines.append(relationships)
        has_relationship_content = True

    # AI 推断的 graph_links（仅 AI 模式生成）
    if graph_links:
        if has_relationship_content:
            lines.append("")
        for item in graph_links:
            target = item.get("target_table", "未知表")
            relation_type = item.get("relation_type", "可能关联")
            join_hint = item.get("join_hint", "未提供")
            confidence = item.get("confidence", "低")
            reason = item.get("reason", "未提供")
            lines.append(
                f"- [[{target}]] · {relation_type} · `{join_hint}` · 置信度：{confidence} · 依据：{reason}"
            )
        has_relationship_content = True

    if not has_relationship_content:
        lines.append("暂无已配置的关联关系。")

    # --- 核心字段解读（仅 AI 模式有内容时渲染） ---
    if core_fields and core_fields not in ("暂无", "暂无字段业务说明。"):
        lines.extend(["", "## 核心字段解读"])
        lines.extend(format_bullet_section(core_fields))

    # --- 注意事项 ---
    lines.extend(["", "## 注意事项"])
    lines.extend(format_bullet_section(summary.get("caveats", "暂无")))

    # --- 字段明细 ---
    lines.extend([
        "",
        "## 字段明细",
        "| 字段名 | 类型 | 原始备注 | 补充备注 |",
        "| --- | --- | --- | --- |",
    ])

    # 预处理备注内容：处理换行符和管道符，避免破坏 Markdown 表格结构
    def clean_comment(c: str | None) -> str:
        if not c:
            return ""
        # 将换行符替换为 <br> 以在单元格内换行
        c = c.replace("\r\n", "<br>").replace("\n", "<br>").replace("\r", "<br>")
        # 转义管道符 | 为 \|
        c = c.replace("|", "\\|")
        return c

    for field in fields:
        orig_c = clean_comment(field.original_comment)
        supp_c = clean_comment(field.supplementary_comment)
        lines.append(
            f"| {field.name} | {field.type} | {orig_c} | {supp_c} |"
        )

    return "\n".join(lines)


def generate_table_summary_basic(
    table: SchemaTable,
    fields: list[SchemaField],
    session: Session = None,
) -> dict[str, str]:
    """基础模式：不调用 AI，仅根据备注和规则生成摘要内容。"""

    # 1. 用途说明
    purpose_parts = []
    if table.original_comment:
        purpose_parts.append(table.original_comment)
    if table.supplementary_comment:
        purpose_parts.append(f"[{table.supplementary_comment}]")

    purpose = " ".join(purpose_parts) if purpose_parts else "暂无业务用途说明，建议补充。"

    # 2. 核心字段解读 — 基础模式下与字段明细表完全重复，跳过
    #    AI 模式由 generate_table_summary() 生成更丰富的业务解读
    
    # 2.5 关联表说明
    related_tables_info = "暂无明确关联表信息。"
    related_wiki_links = []  # 用于 note_properties.related
    relationships_lines = []  # 用于正文 "常见关联关系" 部分
    if table.related_tables and session:
        import json
        names = []
        details_map = {}
        try:
            parsed = json.loads(table.related_tables)
            if isinstance(parsed, dict):
                names = list(parsed.keys())
                details_map = parsed
            else:
                names = [i.strip() for i in table.related_tables.split(",") if i.strip()]
        except:
            try:
                names = [i.strip() for i in table.related_tables.split(",") if i.strip()]
            except:
                pass
        
        if names:
            related_table_objs = session.exec(
                select(SchemaTable).where(
                    SchemaTable.name.in_(names),
                    SchemaTable.datasource_id == table.datasource_id
                )
            ).all()
            if related_table_objs:
                out_names = []
                for t in related_table_objs:
                    detail = details_map.get(t.name, "")
                    detail_str = f" - 关系: {detail}" if detail else ""
                    out_names.append(f"{t.name} ({t.original_comment or '无备注'}){detail_str}")
                    # 构建 wiki link
                    related_wiki_links.append(f"[[{t.name}]]")
                    # 构建关联关系描述
                    if detail:
                        relationships_lines.append(
                            f"- [[{t.name}]]（{t.original_comment or '无备注'}）：{detail}"
                        )
                    else:
                        relationships_lines.append(
                            f"- [[{t.name}]]（{t.original_comment or '无备注'}）"
                        )
                related_tables_info = "\n".join(out_names)

    relationships = "\n".join(relationships_lines) if relationships_lines else None

    # 3. 注意事项 (基于规则)
    has_delete_field = False
    has_status_field = False
    has_time_field = False
    time_field_patterns = (
        "_time",
        "_date",
        "_at",
        "_dt",
        "time_",
        "date_",
        "dt_",
    )
    for f in fields:
        name_low = f.name.lower()
        if any(kw in name_low for kw in ["delete", "del", "is_del"]):
            has_delete_field = True
        if any(kw in name_low for kw in ["status", "state", "type"]):
            has_status_field = True
        if (
            "time" in name_low
            or "date" in name_low
            or name_low.endswith(time_field_patterns)
            or name_low.startswith(time_field_patterns)
            or name_low in {"dt", "at"}
        ):
            has_time_field = True

    caveat_lines = []
    if has_delete_field:
        caveat_lines.append("表中疑似包含逻辑删除标记字段，查询时请确认是否需要过滤已删除数据。")
    if has_status_field:
        caveat_lines.append("表中包含状态或类型字段，使用前请明确状态口径和枚举含义。")
    if has_time_field:
        caveat_lines.append("表中包含时间相关字段，请确认统计口径、时区以及应使用的业务时间字段。")

    caveats = "\n".join(caveat_lines) if caveat_lines else "无特殊注意事项。"

    return {
        "purpose": purpose,
        "related_tables": related_tables_info,
        "relationships": relationships,
        "caveats": caveats,
        "note_properties": {
            "type": "table-note",
            "status": "active",
            "summary": (purpose[:100] + "...") if len(purpose) > 100 else purpose,
            "keywords": [table.name],
            "related": related_wiki_links,
        }
    }


def render_datasource_index_markdown(
    datasource: DataSource,
    task: KnowledgeSyncTask,
    tables: list[SchemaTable],
) -> str:
    lines = [
        f"# {datasource.name}",
        "",
        "## 数据源信息",
        f"- 类型: {datasource.db_type}",
        f"- 表数量: {len(tables)}",
        f"- 生成时间: {(task.finished_at or datetime.now()).strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 表目录",
    ]
    for table in tables:
        lines.append(f"- [[tables/{sanitize_path_segment(table.name)}|{table.name}]]")

    lines.extend(
        [
            "",
            "## 说明",
            "本知识库由 FastGenerate SQL 基于本地已同步 Schema、原始备注与补充备注自动生成。",
        ]
    )
    return "\n".join(lines)


def generate_table_summary(
    session: Session,
    datasource: DataSource,
    table: SchemaTable,
    fields: list[SchemaField],
) -> dict[str, str]:
    sibling_tables = session.exec(
        select(SchemaTable).where(
            SchemaTable.datasource_id == datasource.id,
            SchemaTable.id != table.id
        )
    ).all()
    prompt = _build_summary_prompt(datasource, table, fields, sibling_tables)
    hermes_cli_path = setting_service.get_setting(session, "hermes_cli_path", settings.HERMES_CLI_PATH)
    data = _run_knowledge_summary_with_retry(prompt, hermes_cli_path=hermes_cli_path)
    return {
        "purpose": data.get("purpose", "暂无"),
        "core_fields": data.get("core_fields", "暂无"),
        "related_tables": data.get("related_tables") or data.get("relationships") or "暂无",
        "relationships": data.get("relationships", "暂无"),
        "graph_links": data.get("graph_links", []),
        "note_properties": data.get("note_properties", {}),
        "caveats": data.get("caveats", "暂无"),
    }


def _run_knowledge_summary_with_retry(
    prompt: str,
    *,
    hermes_cli_path: str | None = None,
    max_attempts: int = 2,
) -> dict:
    last_error: RuntimeError | None = None
    for _ in range(max_attempts):
        try:
            return run_hermes_json(prompt, hermes_cli_path=hermes_cli_path)
        except RuntimeError as exc:
            last_error = exc
            if not _is_retryable_knowledge_summary_error(exc):
                raise
    if last_error is not None:
        raise last_error
    raise RuntimeError("知识摘要生成失败")


def _is_retryable_knowledge_summary_error(exc: RuntimeError) -> bool:
    message = str(exc)
    return "Hermes 返回了非 JSON 内容" in message or "Hermes 返回为空" in message



# ---------------------------------------------------------------------------
# SSE 辅助
# ---------------------------------------------------------------------------

def _sse_event(event: str, data: dict) -> str:
    """格式化一个 SSE 事件"""
    import json
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def run_knowledge_sync_task(engine, task_id: int) -> None:
    """后台执行知识库同步。SSE 只订阅进度，不负责驱动任务。"""
    with Session(engine) as session:
        task = session.get(KnowledgeSyncTask, task_id)
        if not task:
            return

        datasource = session.get(DataSource, task.datasource_id)
        if not datasource:
            task.status = KnowledgeSyncTaskStatus.FAILED
            task.error_message = "数据源不存在"
            task.current_phase = "failed"
            task.last_message = task.error_message
            task.finished_at = datetime.now()
            session.add(task)
            session.commit()
            _notify_task_updated(task.id)
            return

        task.status = KnowledgeSyncTaskStatus.RUNNING
        datasource.status = DataSourceStatus.CONNECTION_OK
        datasource.sync_status = SyncStatus.SYNCING
        datasource.last_sync_message = "知识库同步进行中"
        task.started_at = datetime.now()
        task.updated_at = task.started_at
        task.current_phase = "started"
        task.last_message = "知识库同步任务已启动"
        task.current_table = None
        session.add(task)
        session.add(datasource)
        session.commit()
        _notify_task_updated(task.id)

        try:
            output_dir = Path(task.output_dir)
            tables_dir = output_dir / "tables"
            tables_dir.mkdir(parents=True, exist_ok=True)

            # 确定待处理的表列表
            if task.scope == KnowledgeSyncScope.TABLE:
                tables_to_sync = session.exec(
                    select(SchemaTable).where(SchemaTable.id == task.target_table_id)
                ).all()
            else:
                tables_to_sync = session.exec(
                    select(SchemaTable).where(SchemaTable.datasource_id == datasource.id)
                ).all()
            task.total_tables = len(tables_to_sync)
            session.add(task)
            session.commit()
            _notify_task_updated(task.id)

            # 预加载全量表列表，供后续生成 index.md 使用
            all_tables = session.exec(
                select(SchemaTable).where(SchemaTable.datasource_id == datasource.id)
            ).all()

            for idx, table in enumerate(tables_to_sync):
                update_knowledge_task_progress(
                    session,
                    task,
                    "table_start",
                    f"正在处理: {table.name} ({idx + 1}/{len(tables_to_sync)})",
                    table.name,
                )

                try:
                    fields = session.exec(
                        select(SchemaField).where(SchemaField.table_id == table.id)
                    ).all()

                    # 根据模式生成摘要
                    if task.mode == KnowledgeSyncMode.AI_ENHANCED:
                        update_knowledge_task_progress(
                            session,
                            task,
                            "generating_summary",
                            f"正在为 {table.name} 执行 AI 分析...",
                            table.name,
                        )
                        summary = generate_table_summary(session, datasource, table, fields)
                    else:
                        summary = generate_table_summary_basic(table, fields, session=session)
                    
                    markdown = render_table_markdown(datasource, table, fields, summary)
                    table_path = tables_dir / f"{sanitize_path_segment(table.name)}.md"
                    table_path.write_text(markdown, encoding="utf-8")

                    task.completed_tables += 1
                except Exception as table_exc:
                    task.failed_tables += 1
                    error_detail = str(table_exc)[:100]
                    task.error_message = f"表 {table.name} 同步失败: {error_detail}"

                task.updated_at = datetime.now()
                session.add(task)
                session.commit()
                _notify_task_updated(task.id)

            task.finished_at = datetime.now()
            
            # 刷新 index.md（复用已查询的 all_tables）
            index_markdown = render_datasource_index_markdown(datasource, task, all_tables)
            (output_dir / "index.md").write_text(index_markdown, encoding="utf-8")
            
            finalize_knowledge_task_status(task, datasource, total_tables=len(tables_to_sync))
            task.current_table = None
            datasource.status = DataSourceStatus.CONNECTION_OK
            datasource.last_synced_at = task.finished_at
            
            session.add(task)
            session.add(datasource)
            session.commit()
            _notify_task_updated(task.id)

        except Exception as exc:
            task.status = KnowledgeSyncTaskStatus.FAILED
            task.error_message = str(exc)
            task.current_phase = "failed"
            task.last_message = f"知识库同步失败: {str(exc)[:200]}"
            task.current_table = None
            task.finished_at = datetime.now()
            datasource.status = DataSourceStatus.CONNECTION_OK
            datasource.sync_status = SyncStatus.SYNC_FAILED
            datasource.last_sync_message = task.last_message
            datasource.last_synced_at = task.finished_at
            session.add(task)
            session.add(datasource)
            session.commit()
            _notify_task_updated(task.id)


def stream_knowledge_task_events(engine, task_id: int) -> Generator[str, None, None]:
    """订阅知识库同步任务进度；客户端断开不会影响后台任务。"""
    last_signature = None
    last_version = 0
    terminal_statuses = {"completed", "partial_success", "failed"}

    while True:
        with Session(engine) as session:
            task = session.get(KnowledgeSyncTask, task_id)
            if not task:
                yield _sse_event("error", {"message": "任务不存在"})
                return

            payload = knowledge_task_payload(task)
            signature = (
                payload["status"],
                payload["phase"],
                payload["message"],
                payload["completed_tables"],
                payload["failed_tables"],
                payload["total_tables"],
                payload["current_table"],
                payload["error_message"],
            )

            if signature != last_signature:
                yield _sse_event("status", payload)
                last_signature = signature

            if payload["status"] in terminal_statuses:
                _notifier.cleanup(task_id)
                return

        last_version = _notifier.wait(task_id, last_version, timeout=5.0)


def finalize_knowledge_task_status(
    task: KnowledgeSyncTask,
    datasource: DataSource,
    *,
    total_tables: int,
) -> None:
    if task.failed_tables > 0 and task.completed_tables == 0:
        task.status = KnowledgeSyncTaskStatus.FAILED
        task.error_message = task.error_message or "所有表均同步失败"
        task.current_phase = "failed"
        task.last_message = task.error_message
        datasource.sync_status = SyncStatus.SYNC_FAILED
        datasource.last_sync_message = task.error_message
        return

    if task.failed_tables > 0:
        task.status = KnowledgeSyncTaskStatus.PARTIAL_SUCCESS
        detail = (task.error_message or "").strip()
        summary = f"部分完成：{task.failed_tables} 张表失败"
        task.error_message = f"{summary}；{detail}" if detail else summary
        task.current_phase = "completed"
        task.last_message = task.error_message
        datasource.sync_status = SyncStatus.SYNC_PARTIAL_SUCCESS
        datasource.last_sync_message = task.error_message
        return

    task.status = KnowledgeSyncTaskStatus.COMPLETED
    task.error_message = None
    task.current_phase = "completed"
    task.last_message = f"知识库同步完成，共处理 {total_tables} 张表"
    datasource.sync_status = SyncStatus.SYNC_SUCCESS
    datasource.last_sync_message = task.last_message


def _build_summary_prompt(
    datasource: DataSource,
    table: SchemaTable,
    fields: list[SchemaField],
    sibling_tables: list[SchemaTable] | None = None,
) -> str:
    # 提取用户显式标记的关联表 IDs 和关联详情
    user_related_names = set()
    user_related_details = {}
    if table.related_tables:
        import json
        try:
            parsed = json.loads(table.related_tables)
            if isinstance(parsed, dict):
                user_related_names = set(parsed.keys())
                user_related_details = parsed
            else:
                user_related_names = {i.strip() for i in table.related_tables.split(",") if i.strip()}
        except:
            try:
                user_related_names = {i.strip() for i in table.related_tables.split(",") if i.strip()}
            except:
                pass

    field_lines = []
    for field in fields:
        field_lines.append(
            f"- {field.name} ({field.type}) 原始备注: {field.original_comment or '无'}；补充备注: {field.supplementary_comment or '无'}"
        )
    joined_fields = "\n".join(field_lines) if field_lines else "- 无字段"
    
    sibling_lines = []
    user_related_lines = []
    for sibling in sibling_tables or []:
        detail = user_related_details.get(sibling.name, "")
        detail_str = f"；自定义关系: {detail}" if detail else ""
        info = f"- {sibling.name} 原始备注: {sibling.original_comment or '无'}；补充备注: {sibling.supplementary_comment or '无'}{detail_str}"
        if sibling.name in user_related_names:
            user_related_lines.append(info)
        else:
            sibling_lines.append(info)
            
    joined_siblings = "\n".join(sibling_lines) if sibling_lines else "- 无可参考其他表"
    joined_user_related = "\n".join(user_related_lines) if user_related_lines else "- 用户未手动标记关联表"

    return f"""根据下面的数据库元数据，为 Obsidian 生成一张表的结构化知识卡片。

只允许返回一个合法 JSON 对象：
- 不要返回 markdown
- 不要使用 ```json 代码块
- 不要输出任何额外说明
- 所有字符串尽量单行输出
- 只基于输入信息保守总结，不要编造事实
- 输出中文

输入：

数据源: {datasource.name}
数据库类型: {datasource.db_type}
表名: {table.name}
表原始备注: {table.original_comment or '无'}
表补充备注: {table.supplementary_comment or '无'}

字段:
{joined_fields}

同数据源其他表:
{joined_siblings}

用户标记的高强度关联表 (优先考虑):
{joined_user_related}

返回格式：

{{
  "purpose": "",
  "core_fields": "",
  "relationships": "",
  "graph_links": [
    {{
      "target_table": "",
      "relation_type": "",
      "join_hint": "",
      "confidence": "",
      "reason": ""
    }}
  ],
  "note_properties": {{
    "type": "table-note",
    "status": "active",
    "tags": [],
    "summary": "",
    "related": [],
    "domain": "",
    "table_type": "",
    "primary_entities": [],
    "keywords": []
  }},
  "caveats": ""
}}

规则：
1. purpose：1到2句话说明业务用途，以及适合回答什么问题；判断业务用途时要优先参考用户补充备注。
2. core_fields：概括关键字段的业务含义、统计口径、时间口径、状态口径；有枚举值时尽量说明。
3. relationships：用简短文字总结最重要的关联关系，包含关联对象、关联字段、置信度。
4. graph_links：最多5条；只保留最有价值的关联；confidence 只能是“高”“中”“低”；没有明显关联就返回空数组。
5. note_properties.summary：一句话摘要，适合做笔记属性。
6. note_properties.related：尽量输出 wiki link，如 ["[[users]]"]。
7. note_properties.table_type 只能是：事实表、维表、流水表、日志表、配置表、中间表、未知。
8. tags、keywords、primary_entities 尽量简短，方便 Obsidian 检索。
9. 只有在字段名、备注、表名明显支持时，关联置信度才能给“高”；如果只是推测，最多给“中”或“低”。
10. 不确定时明确写“推测”或“需进一步确认”。"""


def build_note_properties(
    datasource: DataSource,
    table: SchemaTable,
    summary: dict[str, str],
    generated_at: datetime,
) -> dict[str, object]:
    note_properties = dict(summary.get("note_properties") or {})
    note_properties.setdefault("project", datasource.name)
    note_properties.setdefault("type", "table-note")
    note_properties.setdefault("status", "active")
    note_properties.setdefault("created", generated_at.strftime("%Y/%m/%d"))
    note_properties.setdefault("updated", generated_at.strftime("%Y/%m/%d"))
    note_properties.setdefault("summary", summary.get("purpose", ""))
    note_properties.setdefault("related", [])
    note_properties.setdefault("tags", [])

    tags = [sanitize_tag(tag) for tag in note_properties.get("tags", []) if tag]
    if "db-table" not in tags:
        tags.insert(0, "db-table")
    note_properties["tags"] = tags

    related = []
    for item in note_properties.get("related", []):
        if item:
            related.append(item)
    for graph_link in summary.get("graph_links", []) or []:
        target_table = graph_link.get("target_table")
        if target_table:
            wiki_link = f"[[{target_table}]]"
            if wiki_link not in related:
                related.append(wiki_link)
    note_properties["related"] = related
    return note_properties


def sanitize_tag(value: str) -> str:
    return value.strip().replace(" ", "-")


def render_frontmatter(properties: dict[str, object]) -> str:
    lines = ["---"]
    for key, value in properties.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                if isinstance(item, str) and item.startswith("[["):
                    lines.append(f'  - "{item}"')
                else:
                    lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def format_bullet_section(text: str) -> list[str]:
    normalized = (text or "").strip()
    if not normalized:
        return ["- 暂无"]

    if "\n" in normalized:
        items = [line.strip(" -") for line in normalized.splitlines() if line.strip()]
        return [f"- {item}" for item in items] or ["- 暂无"]

    numbered = re.split(r"\s*(?:\d+[\.、]\s*)", normalized)
    numbered_items = [item.strip() for item in numbered if item.strip()]
    if len(numbered_items) > 1:
        return [f"- {item}" for item in numbered_items]

    sentences = [item.strip() for item in re.split(r"(?<=。)", normalized) if item.strip()]
    colon_heavy = normalized.count("：") >= 2 or normalized.count(":") >= 2
    if colon_heavy and len(sentences) > 1:
        return [f"- {item}" for item in sentences]

    return [normalized]
