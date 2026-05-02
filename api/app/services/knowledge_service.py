from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator
import threading
import re

from sqlmodel import Session, select

from app.core.config import settings
from app.models.datasource import DataSource, DataSourceStatus, SyncStatus
from app.models.knowledge import KnowledgeSyncTask, KnowledgeSyncTaskStatus
from app.models.schema import SchemaField, SchemaTable
from app.services.hermes_service import run_hermes_json
from app.services import setting_service

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


def get_obsidian_root_path(session: Session) -> str:
    return setting_service.get_setting(session, "obsidian_vault_root", settings.OBSIDIAN_VAULT_ROOT)


def sanitize_path_segment(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "-", value).strip()
    return cleaned or "untitled"


def create_knowledge_sync_task(session: Session, datasource_id: int) -> KnowledgeSyncTask:
    mark_stale_knowledge_sync_tasks(session, datasource_id=datasource_id)

    active_task = get_active_knowledge_sync_task(session, datasource_id)
    if active_task:
        return active_task

    datasource = session.get(DataSource, datasource_id)
    if not datasource:
        raise ValueError("数据源不存在")

    tables = session.exec(
        select(SchemaTable).where(SchemaTable.datasource_id == datasource_id)
    ).all()
    if not tables:
        raise ValueError("未找到已同步表，无法同步到知识库")

    output_root = get_obsidian_root_path(session)
    output_dir = str(Path(output_root) / sanitize_path_segment(datasource.name))
    task = KnowledgeSyncTask(
        datasource_id=datasource.id,
        datasource_name=datasource.name,
        total_tables=len(tables),
        output_root=output_root,
        output_dir=output_dir,
    )
    session.add(task)
    datasource.status = DataSourceStatus.CONNECTION_OK
    datasource.sync_status = SyncStatus.SYNCING
    datasource.last_sync_message = "知识库同步任务已创建"
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
    return session.exec(statement).first()


def get_latest_knowledge_sync_task(session: Session, datasource_id: int) -> KnowledgeSyncTask | None:
    mark_stale_knowledge_sync_tasks(session, datasource_id=datasource_id)

    statement = (
        select(KnowledgeSyncTask)
        .where(KnowledgeSyncTask.datasource_id == datasource_id)
        .order_by(KnowledgeSyncTask.id.desc())
        .limit(1)
    )
    return session.exec(statement).first()


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
    for task in session.exec(statement).all():
        reference_time = task.started_at or task.created_at
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
    session.add(task)
    session.commit()
    _notify_task_updated(task.id)


def knowledge_task_payload(task: KnowledgeSyncTask) -> dict:
    return {
        "task_id": task.id,
        "status": task.status.value if isinstance(task.status, KnowledgeSyncTaskStatus) else task.status,
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
    related_links = note_properties.get("related") or []
    graph_links = summary.get("graph_links") or []

    lines = [
        frontmatter,
        "",
        f"# {table.name}",
        "",
        "[[../index|返回数据源总览]]",
        "",
        "## 基础信息",
        f"- 数据源: {datasource.name}",
        f"- 原始备注: {table.original_comment or '无'}",
        f"- 补充备注: {table.supplementary_comment or '无'}",
        "",
        "## 用途说明",
        summary.get("purpose", "暂无"),
        "",
        "## 核心字段解读",
    ]

    lines.extend(format_bullet_section(summary.get("core_fields", "暂无")))
    lines.extend(
        [
        "",
        "## 关联笔记",
        ]
    )

    if related_links:
        for link in related_links:
            lines.append(f"- {link}")
    else:
        lines.append("- 暂无")

    lines.extend(
        [
        "",
        "## 常见关联关系",
        summary.get("relationships", "暂无"),
        ]
    )
    if graph_links:
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

    lines.extend(
        [
            "",
        "## 注意事项",
        ]
    )
    lines.extend(format_bullet_section(summary.get("caveats", "暂无")))
    lines.extend(
        [
        "",
        "## 字段明细",
        "| 字段名 | 类型 | 原始备注 | 补充备注 |",
        "| --- | --- | --- | --- |",
        ]
    )

    for field in fields:
        lines.append(
            f"| {field.name} | {field.type} | {field.original_comment or ''} | {field.supplementary_comment or ''} |"
        )

    return "\n".join(lines)


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
    data = run_hermes_json(prompt, hermes_cli_path=hermes_cli_path)
    return {
        "purpose": data.get("purpose", "暂无"),
        "core_fields": data.get("core_fields", "暂无"),
        "relationships": data.get("relationships", "暂无"),
        "graph_links": data.get("graph_links", []),
        "note_properties": data.get("note_properties", {}),
        "caveats": data.get("caveats", "暂无"),
    }



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

        tables = session.exec(
            select(SchemaTable).where(SchemaTable.datasource_id == datasource.id)
        ).all()

        task.status = KnowledgeSyncTaskStatus.RUNNING
        datasource.status = DataSourceStatus.CONNECTION_OK
        datasource.sync_status = SyncStatus.SYNCING
        datasource.last_sync_message = "知识库同步进行中"
        task.started_at = datetime.now()
        task.total_tables = len(tables)
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
            
            try:
                tables_dir.mkdir(parents=True, exist_ok=True)
                # 测试写权限
                test_file = tables_dir / ".write_test"
                test_file.write_text("test")
                test_file.unlink()
            except PermissionError as exc:
                raise RuntimeError(f"目录不可写，请检查权限: {output_dir}") from exc
            except OSError as exc:
                raise RuntimeError(f"创建目录失败: {output_dir}") from exc

            for idx, table in enumerate(tables):
                update_knowledge_task_progress(
                    session,
                    task,
                    "table_start",
                    f"开始处理 {table.name}",
                    table.name,
                )

                try:
                    fields = session.exec(
                        select(SchemaField).where(SchemaField.table_id == table.id)
                    ).all()

                    update_knowledge_task_progress(
                        session,
                        task,
                        "generating_summary",
                        f"正在为 {table.name} 生成知识卡片...",
                        table.name,
                    )

                    summary = generate_table_summary(session, datasource, table, fields)
                    markdown = render_table_markdown(datasource, table, fields, summary)
                    table_path = tables_dir / f"{sanitize_path_segment(table.name)}.md"
                    table_path.write_text(markdown, encoding="utf-8")

                    task.completed_tables += 1
                except Exception as table_exc:
                    task.failed_tables += 1
                    task.error_message = f"表 {table.name} 生成失败: {str(table_exc)[:100]}"

                task.current_phase = "table_done"
                task.last_message = f"{table.name} 处理完成"
                task.current_table = None
                session.add(task)
                session.commit()
                _notify_task_updated(task.id)

            task.finished_at = datetime.now()
            index_markdown = render_datasource_index_markdown(datasource, task, tables)
            (output_dir / "index.md").write_text(index_markdown, encoding="utf-8")
            
            if task.failed_tables > 0 and task.completed_tables == 0:
                task.status = KnowledgeSyncTaskStatus.FAILED
                task.error_message = "所有表均同步失败"
                task.current_phase = "failed"
                task.last_message = task.error_message
                datasource.sync_status = SyncStatus.SYNC_FAILED
                datasource.last_sync_message = task.error_message
            elif task.failed_tables > 0:
                task.status = KnowledgeSyncTaskStatus.PARTIAL_SUCCESS
                task.error_message = f"部分完成：{task.failed_tables} 张表失败"
                task.current_phase = "completed"
                task.last_message = task.error_message
                datasource.sync_status = SyncStatus.SYNC_PARTIAL_SUCCESS
                datasource.last_sync_message = task.error_message
            else:
                task.status = KnowledgeSyncTaskStatus.COMPLETED
                task.error_message = None
                task.current_phase = "completed"
                task.last_message = f"知识库同步完成，共处理 {len(tables)} 张表"
                datasource.sync_status = SyncStatus.SYNC_SUCCESS
                datasource.last_sync_message = task.last_message
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


def run_knowledge_sync_stream(engine, task_id: int) -> Generator[str, None, None]:
    """兼容旧端点：订阅已有任务进度，不再由 SSE 驱动同步执行。"""
    yield from stream_knowledge_task_events(engine, task_id)


def _build_summary_prompt(
    datasource: DataSource,
    table: SchemaTable,
    fields: list[SchemaField],
    sibling_tables: list[SchemaTable] | None = None,
) -> str:
    field_lines = []
    for field in fields:
        field_lines.append(
            f"- {field.name} ({field.type}) 原始备注: {field.original_comment or '无'}；补充备注: {field.supplementary_comment or '无'}"
        )
    joined_fields = "\n".join(field_lines) if field_lines else "- 无字段"
    sibling_lines = []
    for sibling in sibling_tables or []:
        sibling_lines.append(
            f"- {sibling.name} 原始备注: {sibling.original_comment or '无'}；补充备注: {sibling.supplementary_comment or '无'}"
        )
    joined_siblings = "\n".join(sibling_lines) if sibling_lines else "- 无可参考其他表"
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
