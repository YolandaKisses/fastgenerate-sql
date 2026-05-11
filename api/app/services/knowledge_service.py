from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import logging
import re
from time import perf_counter
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
from app.models.routine import RoutineDefinition
from app.models.schema import SchemaField, SchemaTable
from app.services.hermes_service import run_deepseek_json
from app.services import setting_service
from app.services.path_utils import sanitize_path_segment

STALE_RUNNING_TASK_AFTER = timedelta(minutes=8)
MAX_PROMPT_SIBLING_TABLES = 8
MAX_PROMPT_ROUTINE_SUMMARIES = 5
MAX_PROMPT_ROUTINE_SNIPPETS = 3

logger = logging.getLogger(__name__)


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


def format_knowledge_timing_log(
    *,
    task_id: int | None,
    table_name: str,
    stage: str,
    elapsed_ms: float,
    extra: dict[str, object] | None = None,
) -> str:
    parts = [
        f"task={task_id}" if task_id is not None else "task=unknown",
        f"table={table_name}",
        f"stage={stage}",
        f"elapsed_ms={elapsed_ms:.2f}",
    ]
    for key, value in sorted((extra or {}).items()):
        parts.append(f"{key}={value}")
    return "knowledge_sync_timing " + " ".join(parts)


def _log_knowledge_timing(
    *,
    task_id: int | None,
    table_name: str,
    stage: str,
    started_at: float,
    extra: dict[str, object] | None = None,
) -> None:
    elapsed_ms = (perf_counter() - started_at) * 1000
    line = format_knowledge_timing_log(
        task_id=task_id,
        table_name=table_name,
        stage=stage,
        elapsed_ms=elapsed_ms,
        extra=extra,
    )
    logger.info(line)
    append_knowledge_timing_log_line(line)


def append_knowledge_timing_log(
    *,
    task_id: int | None,
    table_name: str,
    stage: str,
    elapsed_ms: float,
    extra: dict[str, object] | None = None,
) -> None:
    append_knowledge_timing_log_line(
        format_knowledge_timing_log(
            task_id=task_id,
            table_name=table_name,
            stage=stage,
            elapsed_ms=elapsed_ms,
            extra=extra,
        )
    )


def append_knowledge_timing_log_line(line: str) -> None:
    data_dir = Path(settings.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / "knowledge_sync_timing.log"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"{timestamp} {line}\n")


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
    target_table_id: int | None = None,
    is_incremental: bool = False
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
        is_incremental=is_incremental,
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
        "failed_table_names": task.failed_table_names,
        "error_message": task.error_message,
    }


def render_table_markdown(
    datasource: DataSource,
    table: SchemaTable,
    fields: list[SchemaField],
    summary: dict[str, str],
    generated_at: datetime | None = None,
    existing_table_links: set[str] | None = None,
    existing_routine_names: set[str] | None = None,
) -> str:
    generated_at = generated_at or datetime.now()
    existing_table_links = existing_table_links or set()
    note_properties = build_note_properties(datasource, table, summary, generated_at, fields=fields)
    if existing_table_links:
        note_properties["related"] = [
            item
            for item in note_properties.get("related", [])
            if isinstance(item, str)
            and item.startswith("[[")
            and item.removeprefix("[[").removesuffix("]]") in existing_table_links
        ]
    frontmatter = render_frontmatter(note_properties)
    graph_links = summary.get("graph_links") or []
    relationships = summary.get("relationships")
    core_fields = summary.get("core_fields")

    # --- 标题与面包屑 ---
    lines = [
        frontmatter,
        "",
        f"# 🏷️ {table.name}",
        "",
        "[[../index|⬅️ 返回数据源总览]]",
        "",
    ]

    # --- 概述（Callout 样式） ---
    lines.extend([
        "> [!abstract] 概述",
        f"> - **数据源**: `{datasource.name}`",
        f"> - **业务说明**: {summary.get('purpose', '暂无')}",
        "",
        "---",
        "",
    ])

    # --- 表间关系 ---
    lines.extend([
        "## 🔗 表间关系",
        "> [!link] 关联模型与推断",
    ])
    has_relationship_content = False

    # 用户配置的关联关系
    if relationships:
        # 处理可能的多行关系说明，确保每一行都带 >
        rel_lines = format_bullet_section(relationships)
        for rel in rel_lines:
            lines.append(f"> {rel}")
        has_relationship_content = True

    # AI 推断的 graph_links（仅 AI 模式生成）
    if graph_links:
        if has_relationship_content:
            lines.append("> ")
        for item in graph_links:
            target = item.get("target_table", "未知表")
            relation_type = item.get("relation_type", "可能关联")
            join_hint = item.get("join_hint", "未提供")
            confidence = item.get("confidence", "低")
            reason = item.get("reason", "未提供")
            target_display = f"[[{target}]]" if target in existing_table_links else str(target)
            lines.append(
                f"> - {target_display} · {relation_type} · `{join_hint}` · 置信度：`{confidence}` · 依据：{reason}"
            )
        has_relationship_content = True

    if not has_relationship_content:
        lines.append("> *暂无已配置的关联关系。*")

    lines.append("")
    lines.append("---")

    # --- 核心字段解读 ---
    if core_fields and core_fields not in ("暂无", "暂无字段业务说明。"):
        lines.extend([
            "",
            "## 💡 核心字段解读",
            "> [!quote] 业务逻辑说明",
        ])
        core_items = format_bullet_section(core_fields)
        for item in core_items:
            lines.append(f"> {item}")
        lines.append("")
        lines.append("---")

    # --- 注意事项（Warning Callout） ---
    sanitized_caveats = _sanitize_caveats(summary.get("caveats", "暂无"))
    lines.extend([
        "",
        "## ⚠️ 注意事项",
        "> [!warning] 风险提示",
    ])
    caveat_items = format_bullet_section(sanitized_caveats)
    for item in caveat_items:
        lines.append(f"> {item}")
    
    lines.append("")
    lines.append("---")

    # --- 相关存储过程 ---
    routine_evidence = summary.get("routine_evidence") or []
    lines.extend([
        "",
        "## 🛠️ 相关存储过程",
        "",
        "### 🔍 命中列表",
    ])
    if routine_evidence:
        if (existing_routine_names or set()):
            for item in routine_evidence:
                owner = item.get("owner", "未知")
                name = item.get("name", "未知")
                routine_key = f"{owner}.{name}"
                rtype = item.get("routine_type", "未知")
                if routine_key in (existing_routine_names or set()):
                    lines.append(
                        f"- [[../routines/{sanitize_path_segment(routine_key)}|{routine_key}]] · `{rtype}`"
                    )
                else:
                    lines.append(f"- `{routine_key}` · `{rtype}`")
        else:
            for item in routine_evidence:
                owner = item.get("owner", "未知")
                name = item.get("name", "未知")
                rtype = item.get("routine_type", "未知")
                lines.append(f"- `{owner}.{name}` · `{rtype}`")
    else:
        lines.append("*暂无命中过程*")

    lines.append("")
    lines.append("---")

    # --- 字段明细 ---
    lines.extend([
        "",
        "## 📋 字段明细",
        "",
        "| 字段名 | 类型 | 原始备注 | 补充备注 |",
        "| :--- | :--- | :--- | :--- |",
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
            f"| **{field.name}** | `{field.type}` | {orig_c} | {supp_c} |"
        )

    return "\n".join(lines)



# ── 术语提取 ──

def _collect_terms_from_summaries(
    table_summaries: list[tuple[str, dict[str, str]]],
) -> dict[str, dict[str, object]]:
    """从所有表的 AI 摘要中提取术语定义（来自 business_terms 字段），去重合并。

    每个 term_data 包含 name / aliases / source_tables / definition / evidence。
    同一术语出现于多张表时，取最长的定义并合并 source_tables。
    """
    term_defs: dict[str, str] = {}        # term_name → best definition
    term_sources: dict[str, set[str]] = {}  # term_name → set of table_names

    for table_name, summary in table_summaries:
        business_terms = summary.get("business_terms", []) or []
        for bt in business_terms:
            name = str(bt.get("name", "")).strip()
            definition = str(bt.get("definition", "")).strip()
            if not name or len(name) < 2:
                continue
            # 跳过纯数字/纯英文短标识符
            if name.replace("-", "").replace("_", "").isdigit():
                continue
            if name not in term_sources:
                term_sources[name] = set()
            term_sources[name].add(table_name)
            # 保留最长的定义
            if name not in term_defs or len(definition) > len(term_defs[name]):
                term_defs[name] = definition

    terms: dict[str, dict[str, object]] = {}
    for term_name, source_tables in term_sources.items():
        definition = term_defs.get(term_name, "")
        terms[term_name] = {
            "name": term_name,
            "aliases": [],
            "source_tables": sorted(source_tables),
            "definition": definition if definition else "> 待补充定义。",
            "evidence": f"出现在 {len(source_tables)} 张表的 AI 摘要中",
            "confidence": "中",
        }

    return terms


def render_term_markdown(
    datasource: DataSource,
    term: dict[str, object],
    generated_at: datetime | None = None,
    existing_table_links: set[str] | None = None,
) -> str:
    generated_at = generated_at or datetime.now()
    existing_table_links = existing_table_links or set()
    name = str(term.get("name") or "未命名术语")
    aliases = [str(item) for item in term.get("aliases", []) if item]
    related_tables = [str(item) for item in term.get("source_tables", []) if item]
    lines = [
        render_frontmatter(
            {
                "project": datasource.name,
                "type": "business-term",
                "status": "active",
                "created": generated_at.strftime("%Y/%m/%d"),
                "updated": generated_at.strftime("%Y/%m/%d"),
                "tags": ["business-term"],
                "aliases": aliases,
                "related": [
                    f"[[tables/{sanitize_path_segment(table_name)}|{table_name}]]"
                    for table_name in related_tables
                    if table_name in existing_table_links
                ],
                "confidence": term.get("confidence", "中"),
            }
        ),
        "",
        f"# 📖 {name}",
        "",
        "[[../index|⬅️ 返回数据源总览]]",
        "",
        "> [!info] 业务术语定义",
        f"> {str(term.get('definition') or '暂无定义')}",
        "",
        "---",
        "",
        "## 🔗 相关表",
    ]
    if related_tables:
        for table_name in related_tables:
            if table_name in existing_table_links:
                lines.append(f"- [[../tables/{sanitize_path_segment(table_name)}|{table_name}]]")
            else:
                lines.append(f"- `{table_name}`")
    else:
        lines.append("*暂无*")
    lines.extend([
        "",
        "---",
        "",
        "## 📝 证据与备注",
        f"- **证据**: {term.get('evidence') or '暂无'}",
        f"- **置信度**: `{term.get('confidence', '中')}`",
    ])
    return "\n".join(lines)


def render_metric_markdown(
    datasource: DataSource,
    metric: dict[str, object],
    generated_at: datetime | None = None,
    existing_table_links: set[str] | None = None,
) -> str:
    generated_at = generated_at or datetime.now()
    existing_table_links = existing_table_links or set()
    name = str(metric.get("name") or "未命名指标")
    dimensions = [str(item) for item in metric.get("dimensions", []) if item]
    related_tables = [str(item) for item in metric.get("source_tables", []) if item]
    lines = [
        render_frontmatter(
            {
                "project": datasource.name,
                "type": "metric-definition",
                "status": "active",
                "created": generated_at.strftime("%Y/%m/%d"),
                "updated": generated_at.strftime("%Y/%m/%d"),
                "tags": ["metric-definition"],
                "related": [
                    f"[[tables/{sanitize_path_segment(table_name)}|{table_name}]]"
                    for table_name in related_tables
                    if table_name in existing_table_links
                ],
                "confidence": metric.get("confidence", "中"),
            }
        ),
        "",
        f"# 📊 {name}",
        "",
        "[[../index|⬅️ 返回数据源总览]]",
        "",
        "> [!todo] 指标定义",
        f"> {str(metric.get('definition') or '暂无定义')}",
        "",
        "---",
        "",
        "## 📐 口径说明",
        f"- **公式提示**: `{metric.get('formula_hint') or '暂无'}`",
        f"- **统计粒度**: `{metric.get('grain') or '暂无'}`",
        f"- **时间字段**: `{metric.get('time_field') or '暂无'}`",
        f"- **过滤条件**: `{metric.get('filters') or '暂无'}`",
        "",
        "---",
        "",
        "## 🧊 维度",
    ]
    if dimensions:
        for item in dimensions:
            lines.append(f"- {item}")
    else:
        lines.append("*暂无*")
    lines.extend([
        "",
        "---",
        "",
        "## 🔗 相关表",
    ])
    if related_tables:
        for table_name in related_tables:
            if table_name in existing_table_links:
                lines.append(f"- [[../tables/{sanitize_path_segment(table_name)}|{table_name}]]")
            else:
                lines.append(f"- `{table_name}`")
    else:
        lines.append("*暂无*")
    lines.extend([
        "",
        "---",
        "",
        "## 📝 证据与备注",
        f"- **证据**: {metric.get('evidence') or '暂无'}",
        f"- **置信度**: `{metric.get('confidence', '中')}`",
    ])
    return "\n".join(lines)


def render_join_pattern_markdown(
    datasource: DataSource,
    join_pattern: dict[str, object],
    generated_at: datetime | None = None,
    existing_table_links: set[str] | None = None,
) -> str:
    generated_at = generated_at or datetime.now()
    existing_table_links = existing_table_links or set()
    name = str(join_pattern.get("name") or "未命名关联模式")
    left_table = str(join_pattern.get("left_table") or "未知表")
    right_table = str(join_pattern.get("right_table") or "未知表")
    lines = [
        render_frontmatter(
            {
                "project": datasource.name,
                "type": "join-pattern",
                "status": "active",
                "created": generated_at.strftime("%Y/%m/%d"),
                "updated": generated_at.strftime("%Y/%m/%d"),
                "tags": ["join-pattern"],
                "related": [
                    f"[[tables/{sanitize_path_segment(table_name)}|{table_name}]]"
                    for table_name in [left_table, right_table]
                    if table_name in existing_table_links
                ],
                "confidence": join_pattern.get("confidence", "中"),
            }
        ),
        "",
        f"# 🔗 {name}",
        "",
        "[[../index|⬅️ 返回数据源总览]]",
        "",
        "> [!link] 关联定义",
        f"> **关联对象**: ",
    ]
    
    if left_table in existing_table_links:
        lines.append(f"> - [[../tables/{sanitize_path_segment(left_table)}|{left_table}]]")
    else:
        lines.append(f"> - `{left_table}`")
        
    if right_table in existing_table_links:
        lines.append(f"> - [[../tables/{sanitize_path_segment(right_table)}|{right_table}]]")
    else:
        lines.append(f"> - `{right_table}`")

    lines.extend([
        "",
        "---",
        "",
        "## 🛠️ 关联条件",
        f"```sql",
        f"{join_pattern.get('join_condition') or '暂无'}",
        f"```",
        "",
        "## 💡 使用场景",
        f"{join_pattern.get('usage') or '暂无'}",
        "",
        "---",
        "",
        "## 📝 证据与备注",
        f"- **证据**: {join_pattern.get('evidence') or '暂无'}",
        f"- **置信度**: `{join_pattern.get('confidence', '中')}`",
    ])
    return "\n".join(lines)


def render_routine_markdown(
    datasource: DataSource,
    routine: RoutineDefinition,
    related_tables: list[str] | None = None,
    generated_at: datetime | None = None,
    existing_table_links: set[str] | None = None,
) -> str:
    generated_at = generated_at or datetime.now()
    routine_name = f"{routine.owner}.{routine.name}"
    related_tables = related_tables or []
    existing_table_links = existing_table_links or set()
    lines = [
        render_frontmatter(
            {
                "project": datasource.name,
                "type": "routine-note",
                "status": "active",
                "created": generated_at.strftime("%Y/%m/%d"),
                "updated": generated_at.strftime("%Y/%m/%d"),
                "tags": ["routine-note"],
                "related": [
                    f"[[tables/{sanitize_path_segment(table_name)}|{table_name}]]"
                    for table_name in related_tables
                    if table_name in existing_table_links
                ],
                "routine_type": routine.routine_type,
            }
        ),
        "",
        f"# ⚙️ {routine_name}",
        "",
        "[[../index|⬅️ 返回数据源总览]]",
        "",
        "> [!info] 存储过程信息",
        f"> - **所属 Schema**: `{routine.owner}`",
        f"> - **类型**: `{routine.routine_type}`",
        "",
        "---",
        "",
        "## 🔗 相关表",
    ]
    if related_tables:
        for table_name in related_tables:
            if table_name in existing_table_links:
                lines.append(f"- [[../tables/{sanitize_path_segment(table_name)}|{table_name}]]")
            else:
                lines.append(f"- `{table_name}`")
    else:
        lines.append("*暂无*")
    lines.extend([
        "",
        "---",
        "",
        "## 📜 源码",
        "```sql",
        routine.definition_text or "",
        "```",
    ])
    return "\n".join(lines)


def _merge_string_lists(existing: list[str], incoming: list[str]) -> list[str]:
    merged = list(existing)
    for item in incoming:
        if item and item not in merged:
            merged.append(item)
    return merged


def _register_named_page(
    store: dict[str, dict[str, object]],
    *,
    key: str,
    payload: dict[str, object],
    list_fields: list[str] | None = None,
) -> None:
    current = store.get(key)
    if not current:
        store[key] = payload
        return
    for field in list_fields or []:
        current[field] = _merge_string_lists(
            [str(item) for item in current.get(field, []) if item],
            [str(item) for item in payload.get(field, []) if item],
        )
    for field, value in payload.items():
        if field in (list_fields or []):
            continue
        if not current.get(field) and value:
            current[field] = value


def collect_structured_pages(
    datasource: DataSource,
    table: SchemaTable,
    summary: dict[str, object],
) -> dict[str, list[dict[str, object]]]:
    terms: list[dict[str, object]] = []
    metrics: list[dict[str, object]] = []
    join_patterns: list[dict[str, object]] = []

    raw_terms = summary.get("terms") or []
    if not raw_terms:
        for entity in (summary.get("note_properties") or {}).get("primary_entities", []):
            if entity:
                raw_terms.append(
                    {
                        "name": entity,
                        "definition": summary.get("purpose") or "暂无定义",
                        "confidence": "中",
                        "evidence": "来自表卡摘要与主实体推断",
                    }
                )
    for item in raw_terms:
        name = str(item.get("name") or "").strip() if isinstance(item, dict) else ""
        if not name:
            continue
        terms.append(
            {
                "name": name,
                "definition": item.get("definition") or summary.get("purpose") or "暂无定义",
                "aliases": [str(alias) for alias in item.get("aliases", []) if alias],
                "confidence": item.get("confidence") or "中",
                "evidence": item.get("evidence") or "来自知识卡摘要",
                "source_tables": [table.name],
            }
        )

    for item in summary.get("metrics") or []:
        name = str(item.get("name") or "").strip() if isinstance(item, dict) else ""
        if not name:
            continue
        metrics.append(
            {
                "name": name,
                "definition": item.get("definition") or "暂无定义",
                "formula_hint": item.get("formula_hint") or "",
                "grain": item.get("grain") or "",
                "dimensions": [str(dim) for dim in item.get("dimensions", []) if dim],
                "filters": item.get("filters") or "",
                "time_field": item.get("time_field") or "",
                "confidence": item.get("confidence") or "中",
                "evidence": item.get("evidence") or "来自知识卡摘要",
                "source_tables": [table.name],
            }
        )

    raw_join_patterns = list(summary.get("join_patterns") or [])
    if not raw_join_patterns:
        for item in summary.get("graph_links") or []:
            target_table = item.get("target_table")
            if not target_table:
                continue
            raw_join_patterns.append(
                {
                    "name": f"{table.name}关联{target_table}",
                    "left_table": table.name,
                    "right_table": target_table,
                    "join_condition": item.get("join_hint") or "",
                    "usage": item.get("relation_type") or "常见关联路径",
                    "confidence": item.get("confidence") or "中",
                    "evidence": item.get("reason") or "来自 graph_links 推断",
                }
            )
    for item in raw_join_patterns:
        name = str(item.get("name") or "").strip() if isinstance(item, dict) else ""
        if not name:
            continue
        join_patterns.append(
            {
                "name": name,
                "left_table": item.get("left_table") or table.name,
                "right_table": item.get("right_table") or "",
                "join_condition": item.get("join_condition") or item.get("join_hint") or "",
                "usage": item.get("usage") or item.get("relation_type") or "常见关联路径",
                "confidence": item.get("confidence") or "中",
                "evidence": item.get("evidence") or item.get("reason") or "来自知识卡摘要",
            }
        )

    return {
        "terms": terms,
        "metrics": metrics,
        "join_patterns": join_patterns,
    }


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
        "graph_links": [],
        "routine_evidence": [],
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
    routine_names: list[str] | None = None,
    term_names: list[str] | None = None,
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
        brief = (table.supplementary_comment or table.original_comment or "").strip()
        if brief:
            brief = brief[:80] + ("..." if len(brief) > 80 else "")
            lines.append(f"- [[tables/{sanitize_path_segment(table.name)}|{table.name}]] — {brief}")
        else:
            lines.append(f"- [[tables/{sanitize_path_segment(table.name)}|{table.name}]]")

    if routine_names:
        lines.extend([
            "",
            f"## 存储过程（{len(routine_names)} 个）",
        ])
        for rname in sorted(routine_names):
            lines.append(f"- [[routines/{sanitize_path_segment(rname)}|{rname}]]")

    if term_names:
        lines.extend([
            "",
            f"## 业务术语（{len(term_names)} 个）",
        ])
        for tname in sorted(term_names):
            lines.append(f"- [[terms/{sanitize_path_segment(tname)}|{tname}]]")

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
    overall_started = perf_counter()
    sibling_started = perf_counter()
    sibling_tables = session.exec(
        select(SchemaTable).where(
            SchemaTable.datasource_id == datasource.id,
            SchemaTable.id != table.id
        )
    ).all()
    _log_knowledge_timing(
        task_id=None,
        table_name=table.name,
        stage="load_sibling_tables",
        started_at=sibling_started,
        extra={"count": len(sibling_tables)},
    )
    routine_started = perf_counter()
    related_routines = get_related_routines_for_table(
        session,
        datasource_id=datasource.id,
        table=table,
    )
    _log_knowledge_timing(
        task_id=None,
        table_name=table.name,
        stage="load_related_routines",
        started_at=routine_started,
        extra={"count": len(related_routines)},
    )
    prompt_started = perf_counter()
    prompt = _build_summary_prompt(
        datasource,
        table,
        fields,
        sibling_tables,
        related_routines,
    )
    _log_knowledge_timing(
        task_id=None,
        table_name=table.name,
        stage="build_prompt",
        started_at=prompt_started,
        extra={"prompt_len": len(prompt)},
    )
    hermes_started = perf_counter()
    data = run_deepseek_json(prompt)
    _log_knowledge_timing(
        task_id=None,
        table_name=table.name,
        stage="hermes_call",
        started_at=hermes_started,
        extra={"prompt_len": len(prompt), "routine_count": len(related_routines)},
    )
    _log_knowledge_timing(
        task_id=None,
        table_name=table.name,
        stage="generate_table_summary_total",
        started_at=overall_started,
        extra={"prompt_len": len(prompt)},
    )
    return {
        "purpose": data.get("purpose", "暂无"),
        "core_fields": data.get("core_fields", "暂无"),
        "related_tables": data.get("related_tables") or data.get("relationships") or "暂无",
        "relationships": data.get("relationships", "暂无"),
        "graph_links": data.get("graph_links", []),
        "note_properties": data.get("note_properties", {}),
        "caveats": data.get("caveats", "暂无"),
        "routine_evidence": build_related_routine_evidence(related_routines, table.name),
        "business_terms": data.get("business_terms", []),
        "_source": "ai",
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
            routines_dir = output_dir / "routines"
            routines_dir.mkdir(parents=True, exist_ok=True)
            terms_dir = output_dir / "terms"
            terms_dir.mkdir(parents=True, exist_ok=True)

            # 确定待处理的表列表
            if task.scope == KnowledgeSyncScope.TABLE:
                tables_to_sync = session.exec(
                    select(SchemaTable).where(SchemaTable.id == task.target_table_id)
                ).all()
            else:
                tables_to_sync = session.exec(
                    select(SchemaTable).where(SchemaTable.datasource_id == datasource.id)
                ).all()

                # ── 全量同步：清空 tables/ routines/ terms/，重建 ──
                if not task.is_incremental:
                    for _d in (tables_dir, routines_dir, terms_dir):
                        if _d.exists():
                            for _f in _d.iterdir():
                                if _f.is_file():
                                    _f.unlink()

            task.total_tables = len(tables_to_sync)
            session.add(task)
            session.commit()
            _notify_task_updated(task.id)

            # 预加载全量表列表，供后续生成 index.md 使用
            all_tables = session.exec(
                select(SchemaTable).where(SchemaTable.datasource_id == datasource.id)
            ).all()

            # ── 预扫描：构建 routine → 引用表的映射，生成 routine 实体页 ──
            # 始终扫全量表获取完整引用关系，但单表同步只写涉及该表的 routine
            existing_routine_names: set[str] = set()
            all_table_names: set[str] = {t.name for t in all_tables}
            is_full_sync = task.scope != KnowledgeSyncScope.TABLE
            synced_table_name: str | None = (
                tables_to_sync[0].name if not is_full_sync and tables_to_sync else None
            )

            routine_map = build_routine_table_map(
                session, datasource_id=datasource.id, tables=all_tables
            )
            for routine_key, (routine_def, referenced_tables) in routine_map.items():
                if not is_full_sync:
                    # 单表同步：只写引用当前表的 routine
                    if synced_table_name not in referenced_tables:
                        continue
                routine_markdown = render_routine_markdown(
                    datasource,
                    routine_def,
                    related_tables=sorted(referenced_tables),
                    existing_table_links=all_table_names,
                )
                routine_filename = f"{sanitize_path_segment(routine_key)}.md"
                (routines_dir / routine_filename).write_text(
                    routine_markdown, encoding="utf-8"
                )
                existing_routine_names.add(routine_key)

            # ── 收集表摘要（供后续术语提取） ──
            table_summaries: list[tuple[str, dict[str, str]]] = []
            failed_table_names_list: list[str] = []

            for idx, table in enumerate(tables_to_sync):
                table_started = perf_counter()
                update_knowledge_task_progress(
                    session,
                    task,
                    "table_start",
                    f"正在处理: {table.name} ({idx + 1}/{len(tables_to_sync)})",
                    table.name,
                )

                try:
                    fields_started = perf_counter()
                    fields = session.exec(
                        select(SchemaField).where(SchemaField.table_id == table.id)
                    ).all()
                    _log_knowledge_timing(
                        task_id=task.id,
                        table_name=table.name,
                        stage="load_fields",
                        started_at=fields_started,
                        extra={"count": len(fields)},
                    )

                    # 根据模式生成摘要
                    if task.mode == KnowledgeSyncMode.AI_ENHANCED:
                        update_knowledge_task_progress(
                            session,
                            task,
                            "generating_summary",
                            f"正在为 {table.name} 执行 AI 分析...",
                            table.name,
                        )
                        # 增量模式：如果文件已存在且不是手动页面，尝试跳过
                        table_path = tables_dir / f"{sanitize_path_segment(table.name)}.md"
                        if task.is_incremental and table_path.exists():
                            # 简单起见：只要存在就跳过。如果需要强制更新，用户可以使用全量同步。
                            # 这里可以增加更复杂的判断，比如校验备注是否更新。
                            task.completed_tables += 1
                            table_summaries.append((table.name, {"_source": "skipped"})) # 占位
                            continue

                        summary_started = perf_counter()
                        summary = generate_table_summary(session, datasource, table, fields)
                        _log_knowledge_timing(
                            task_id=task.id,
                            table_name=table.name,
                            stage="generate_ai_summary",
                            started_at=summary_started,
                            extra={"mode": task.mode},
                        )
                    else:
                        # 增量模式同样适用于基础同步
                        table_path = tables_dir / f"{sanitize_path_segment(table.name)}.md"
                        if task.is_incremental and table_path.exists():
                            task.completed_tables += 1
                            table_summaries.append((table.name, {"_source": "skipped"}))
                            continue

                        summary_started = perf_counter()
                        summary = generate_table_summary_basic(table, fields, session=session)
                        related_routines = get_related_routines_for_table(
                            session,
                            datasource_id=datasource.id,
                            table=table,
                        )
                        summary["routine_evidence"] = build_related_routine_evidence(
                            related_routines,
                            table.name,
                        )
                        _log_knowledge_timing(
                            task_id=task.id,
                            table_name=table.name,
                            stage="generate_basic_summary",
                            started_at=summary_started,
                            extra={"routine_count": len(related_routines)},
                        )

                    existing_table_links = {item.name for item in tables_to_sync}
                    render_started = perf_counter()
                    markdown = render_table_markdown(
                        datasource,
                        table,
                        fields,
                        summary,
                        existing_table_links=existing_table_links,
                        existing_routine_names=existing_routine_names,
                    )
                    table_path = tables_dir / f"{sanitize_path_segment(table.name)}.md"

                    # ── 人工页面保护 ──
                    if table_path.exists():
                        existing_frontmatter = _read_frontmatter(table_path)
                        existing_source = existing_frontmatter.get("source", "")
                        if existing_source == "manual":
                            _log_knowledge_timing(
                                task_id=task.id,
                                table_name=table.name,
                                stage="skip_manual_protected",
                                extra={"reason": "人工标记 source=manual，跳过覆盖"},
                            )
                            task.completed_tables += 1
                            continue
                        # hybrid 模式：保留人工备注，仅更新 AI 段落
                        if existing_source == "hybrid":
                            manual_sections = _extract_manual_sections(table_path)
                            if manual_sections:
                                markdown = _merge_hybrid_content(markdown, manual_sections)

                    table_path.write_text(markdown, encoding="utf-8")
                    _log_knowledge_timing(
                        task_id=task.id,
                        table_name=table.name,
                        stage="render_and_write_markdown",
                        started_at=render_started,
                        extra={"markdown_len": len(markdown)},
                    )

                    task.completed_tables += 1
                    table_summaries.append((table.name, summary))
                except Exception as table_exc:
                    task.failed_tables += 1
                    failed_table_names_list.append(table.name)
                    error_detail = str(table_exc)[:100]
                    task.error_message = f"表 {table.name} 同步失败: {error_detail}"

                task.updated_at = datetime.now()
                session.add(task)
                session.commit()
                _notify_task_updated(task.id)
                _log_knowledge_timing(
                    task_id=task.id,
                    table_name=table.name,
                    stage="table_total",
                    started_at=table_started,
                    extra={"status": "failed" if task.error_message else "completed"},
                )

            task.finished_at = datetime.now()

            # ── 术语页面生成 ──
            # 术语自然跟随 tables_to_sync 范围：全量同步得全部，单表同步得该表的
            existing_term_names: set[str] = set()
            if table_summaries:
                terms_map = _collect_terms_from_summaries(table_summaries)
                for term_name, term_data in terms_map.items():
                    term_markdown = render_term_markdown(
                        datasource,
                        term_data,
                        existing_table_links=all_table_names,
                    )
                    term_filename = f"{sanitize_path_segment(term_name)}.md"
                    (terms_dir / term_filename).write_text(
                        term_markdown, encoding="utf-8"
                    )
                    existing_term_names.add(term_name)

            # 刷新 index.md（确保使用 all_tables 而不是仅本次同步的 tables_to_sync）
            # 对于存储过程：直接使用 routine_map 中的全量键，确保索引完整
            # 对于术语：由于没有数据库记录，从 terms 目录扫描已有的文件
            final_term_names = set(existing_term_names)
            if terms_dir.exists():
                for _f in terms_dir.glob("*.md"):
                    final_term_names.add(_f.stem)

            index_markdown = render_datasource_index_markdown(
                datasource, task, all_tables,
                routine_names=sorted(list(routine_map.keys())),
                term_names=sorted(list(final_term_names)),
            )
            (output_dir / "index.md").write_text(index_markdown, encoding="utf-8")
            
            import json
            task.failed_table_names = json.dumps(failed_table_names_list, ensure_ascii=False) if failed_table_names_list else None
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


def get_related_routines_for_table(
    session: Session,
    *,
    datasource_id: int,
    table: SchemaTable,
) -> list[RoutineDefinition]:
    table_name = (table.name or "").strip().lower()
    if not table_name:
        return []

    routines = session.exec(
        select(RoutineDefinition)
        .where(RoutineDefinition.datasource_id == datasource_id)
        .order_by(RoutineDefinition.owner, RoutineDefinition.routine_type, RoutineDefinition.name)
    ).all()

    matched: list[RoutineDefinition] = []
    for routine in routines:
        if table_name in (routine.definition_text or "").lower():
            matched.append(routine)
    return matched


def build_routine_table_map(
    session: Session,
    *,
    datasource_id: int,
    tables: list[SchemaTable],
) -> dict[str, tuple[RoutineDefinition, set[str]]]:
    """构建 routine → (routine对象, 引用它的表名集合) 的映射。

    用于预扫描阶段：在生成表页之前，先生成 routine 实体页，
    使表页可以用 [[../routines/name]] 链接替代嵌入 SQL。
    """
    routines = session.exec(
        select(RoutineDefinition).where(
            RoutineDefinition.datasource_id == datasource_id
        )
    ).all()

    routine_map: dict[str, tuple[RoutineDefinition, set[str]]] = {}
    for routine in routines:
        key = f"{routine.owner}.{routine.name}"
        referenced_tables: set[str] = set()
        routine_text = (routine.definition_text or "").lower()
        for table in tables:
            table_name = (table.name or "").strip().lower()
            if table_name and table_name in routine_text:
                referenced_tables.add(table.name)
        
        # 无论是否命中表，都包含进来，确保“存储过程”完整
        routine_map[key] = (routine, referenced_tables)
    return routine_map


def _parse_related_table_config(table: SchemaTable) -> tuple[set[str], dict[str, str]]:
    user_related_names = set()
    user_related_details: dict[str, str] = {}
    if table.related_tables:
        import json
        try:
            parsed = json.loads(table.related_tables)
            if isinstance(parsed, dict):
                user_related_names = set(parsed.keys())
                user_related_details = {str(k): str(v) for k, v in parsed.items()}
            else:
                user_related_names = {i.strip() for i in table.related_tables.split(",") if i.strip()}
        except Exception:
            try:
                user_related_names = {i.strip() for i in table.related_tables.split(",") if i.strip()}
            except Exception:
                pass
    return user_related_names, user_related_details


def _table_name_tokens(value: str) -> set[str]:
    return {token for token in re.split(r"[_\W]+", value.lower()) if token}


def select_high_relevance_sibling_tables(
    *,
    current_table: SchemaTable,
    siblings: list[SchemaTable],
    fields: list[SchemaField],
    related_routines: list[RoutineDefinition],
    limit: int = MAX_PROMPT_SIBLING_TABLES,
) -> list[SchemaTable]:
    user_related_names, _ = _parse_related_table_config(current_table)
    current_tokens = _table_name_tokens(current_table.name or "")
    field_tokens: set[str] = set()
    for field in fields:
        field_tokens.update(_table_name_tokens(getattr(field, "name", "")))
    routine_text = "\n".join((routine.definition_text or "").lower() for routine in related_routines)

    scored: list[tuple[int, int, str, SchemaTable]] = []
    for sibling in siblings:
        score = 0
        sibling_name = sibling.name or ""
        sibling_lower = sibling_name.lower()
        sibling_tokens = _table_name_tokens(sibling_name)

        if sibling_name in user_related_names:
            score += 100
        if current_tokens & sibling_tokens:
            score += 40
        if sibling_lower in routine_text:
            score += 20
        if sibling.original_comment or sibling.supplementary_comment:
            score += 10
        if field_tokens & sibling_tokens:
            score += 10
        if sibling_lower.startswith(("tmp_", "temp_", "test_")):
            score -= 20

        scored.append(
            (
                score,
                1 if (sibling.original_comment or sibling.supplementary_comment) else 0,
                sibling_name,
                sibling,
            )
        )

    scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [item[3] for item in scored[:limit]]


def _format_related_routines_for_prompt(routines: list[RoutineDefinition]) -> str:
    if not routines:
        return "- 无命中的存储过程"

    blocks: list[str] = []
    for routine in routines:
        blocks.append(
            "\n".join(
                [
                    f"过程名: {routine.name}",
                    f"所属 Schema: {routine.owner}",
                    f"类型: {routine.routine_type}",
                    "原文:",
                    routine.definition_text or "无原文",
                ]
            )
        )
    return "\n\n".join(blocks)


def _infer_routine_table_role(definition_text: str, table_name: str) -> str:
    lowered = definition_text.lower()
    table = re.escape(table_name.lower())
    roles = []
    if re.search(rf"\binsert\s+into\s+{table}\b", lowered):
        roles.append("insert_into")
    if re.search(rf"\bupdate\s+{table}\b", lowered):
        roles.append("update")
    if re.search(rf"\bdelete\s+from\s+{table}\b", lowered):
        roles.append("delete_from")
    if re.search(rf"\bfrom\s+{table}\b", lowered):
        roles.append("select_from")
    if re.search(rf"\bjoin\s+{table}\b", lowered):
        roles.append("join_ref")
    if not roles:
        return "reference"
    if len(roles) == 1:
        return roles[0]
    return "mixed"


def _build_routine_summary(
    routine: RoutineDefinition,
    *,
    table_name: str,
    sibling_tables: list[SchemaTable],
) -> dict[str, object]:
    definition_text = routine.definition_text or ""
    lowered = definition_text.lower()
    matched_count = lowered.count(table_name.lower())
    related_tables = []
    for sibling in sibling_tables:
        sibling_name = sibling.name or ""
        if sibling_name.lower() in lowered:
            related_tables.append(sibling_name)
    related_tables = related_tables[:5]
    table_role = _infer_routine_table_role(definition_text, table_name)
    if table_role == "insert_into":
        summary = "该过程向当前表写入数据。"
    elif table_role == "update":
        summary = "该过程更新当前表中的记录。"
    elif table_role == "delete_from":
        summary = "该过程删除当前表中的记录。"
    elif table_role == "select_from":
        summary = "该过程读取当前表数据。"
    elif table_role == "join_ref":
        summary = "该过程将当前表作为关联对象引用。"
    else:
        summary = "该过程对当前表存在读写混合或多步骤引用。"
    return {
        "owner": routine.owner,
        "name": routine.name,
        "routine_type": routine.routine_type,
        "table_role": table_role,
        "matched_count": matched_count,
        "related_tables": related_tables,
        "summary": summary,
        "snippet": _extract_routine_snippet(definition_text, table_name),
    }


def _format_related_routine_summaries_for_prompt(
    routines: list[RoutineDefinition],
    *,
    table_name: str,
    sibling_tables: list[SchemaTable],
) -> str:
    if not routines:
        return "- 无命中的存储过程"

    lines: list[str] = []
    for routine in routines[:MAX_PROMPT_ROUTINE_SUMMARIES]:
        item = _build_routine_summary(routine, table_name=table_name, sibling_tables=sibling_tables)
        related_tables = ", ".join(item["related_tables"]) if item["related_tables"] else "无"
        lines.append(
            f"- {item['owner']}.{item['name']}｜{item['routine_type']}｜当前表角色: {item['table_role']}｜命中: {item['matched_count']} 次｜相关表: {related_tables}｜摘要: {item['summary']}"
        )
    return "\n".join(lines)


def _format_related_routine_snippets_for_prompt(
    routines: list[RoutineDefinition],
    *,
    table_name: str,
    sibling_tables: list[SchemaTable],
) -> str:
    if not routines:
        return "- 无关键片段"

    lines: list[str] = []
    for routine in routines[:MAX_PROMPT_ROUTINE_SNIPPETS]:
        item = _build_routine_summary(routine, table_name=table_name, sibling_tables=sibling_tables)
        lines.extend(
            [
                f"[{item['owner']}.{item['name']}]",
                item["snippet"] or "无可展示片段",
                "",
            ]
        )
    return "\n".join(lines).strip()


def _extract_routine_snippet(definition_text: str, table_name: str) -> str:
    lines = definition_text.splitlines()
    lowered_table_name = table_name.lower()
    matching_indexes = [
        idx for idx, line in enumerate(lines) if lowered_table_name in line.lower()
    ]

    if not lines:
        return ""

    if not matching_indexes:
        return "\n".join(lines[:12]).strip()

    start = max(0, matching_indexes[0] - 2)
    end = min(len(lines), matching_indexes[-1] + 3)
    return "\n".join(lines[start:end]).strip()


def build_related_routine_evidence(
    routines: list[RoutineDefinition],
    table_name: str,
) -> list[dict[str, str]]:
    evidence: list[dict[str, str]] = []
    for routine in routines:
        evidence.append(
            {
                "owner": routine.owner,
                "name": routine.name,
                "routine_type": routine.routine_type,
                "snippet": _extract_routine_snippet(routine.definition_text or "", table_name),
            }
        )
    return evidence


def _sanitize_caveats(caveats: str | None) -> str:
    text = (caveats or "").strip()
    if not text:
        return "暂无"

    patterns = [
        r"未命中任何存储过程原文，上下游调用关系无法验证。?",
        r"未命中存储过程原文，上下游调用关系无法验证。?",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text)

    text = re.sub(r"\s+", " ", text).strip(" ；;，,。")
    return text or "暂无"


def _build_summary_prompt(
    datasource: DataSource,
    table: SchemaTable,
    fields: list[SchemaField],
    sibling_tables: list[SchemaTable] | None = None,
    related_routines: list[RoutineDefinition] | None = None,
) -> str:
    user_related_names, user_related_details = _parse_related_table_config(table)

    field_lines = []
    for field in fields:
        field_lines.append(
            f"- {field.name} ({field.type}) 原始备注: {field.original_comment or '无'}；补充备注: {field.supplementary_comment or '无'}"
        )
    joined_fields = "\n".join(field_lines) if field_lines else "- 无字段"

    selected_siblings = select_high_relevance_sibling_tables(
        current_table=table,
        siblings=sibling_tables or [],
        fields=fields,
        related_routines=related_routines or [],
    )

    sibling_lines = []
    user_related_lines = []
    for sibling in selected_siblings:
        detail = user_related_details.get(sibling.name, "")
        reason_parts = []
        if sibling.name in user_related_names:
            reason_parts.append("用户手工标记")
        if sibling.original_comment or sibling.supplementary_comment:
            reason_parts.append("存在表备注")
        if (sibling.name or "").lower() in "\n".join((routine.definition_text or "").lower() for routine in related_routines or []):
            reason_parts.append("命中同一存储过程")
        reason = "、".join(reason_parts) if reason_parts else "名称或上下文相关"
        detail_str = f"；自定义关系: {detail}" if detail else ""
        info = f"- {sibling.name} 原始备注: {sibling.original_comment or '无'}；补充备注: {sibling.supplementary_comment or '无'}{detail_str}；原因: {reason}"
        if sibling.name in user_related_names:
            user_related_lines.append(info)
        else:
            sibling_lines.append(info)
            
    joined_siblings = "\n".join(sibling_lines) if sibling_lines else "- 无高相关其他表"
    joined_user_related = "\n".join(user_related_lines) if user_related_lines else "- 用户未手动标记关联表"
    joined_related_routine_summaries = _format_related_routine_summaries_for_prompt(
        related_routines or [],
        table_name=table.name,
        sibling_tables=selected_siblings,
    )
    joined_related_routine_snippets = _format_related_routine_snippets_for_prompt(
        related_routines or [],
        table_name=table.name,
        sibling_tables=selected_siblings,
    )

    return f"""根据下面的数据库元数据，为 Obsidian 生成一张表的结构化知识卡片。只返回合法 JSON（不要 markdown / 代码块 / 额外说明），中文输出，保守总结不编造。

输入：

数据源: {datasource.name}
数据库类型: {datasource.db_type}
表名: {table.name}
表原始备注: {table.original_comment or '无'}
表补充备注: {table.supplementary_comment or '无'}

字段:
{joined_fields}

高相关其他表:
{joined_siblings}

用户标记的高强度关联表 (优先考虑):
{joined_user_related}

相关存储过程摘要:
{joined_related_routine_summaries}

相关存储过程关键片段:
{joined_related_routine_snippets}

规则：
1. purpose：1-2 句业务用途，优先参考用户补充备注。
2. core_fields：关键字段的业务含义、统计口径，有枚举值时注明。请以换行或列表形式提供，确保清晰易读。
3. relationships：最重要关联（对象、字段、置信度）。
4. graph_links：最有价值关联，confidence 仅限 高/中/低，无关联返回 []；各项可选 target_table / relation_type / confidence。
5. note_properties.summary 一句话；table_type 仅限 事实表/维表/流水表/日志表/配置表/中间表/未知；tags / keywords 简短；related 用 wiki link 格式 [[表名]]。
6. 置信度仅当字段名/备注明显支撑时给"高"，推测最多"中/低"，不确定写"推测"。
7. 利用存储过程信息增强，但不编造不存在的事实。
8. 仅在输出内容（如 purpose, core_fields）中禁用英文双引号，改用单引号或书名号，但 JSON 结构本身的键值对必须使用标准的英文双引号。
9. 只输出必需信息，不额外扩展。
10. business_terms：从当前表提取 1-5 个核心业务术语（跨表通用的业务概念，非表名或字段名），给出 1-2 句简明定义。

返回格式：{{"purpose":"","core_fields":"","relationships":"","graph_links":[],"note_properties":{{"summary":"","table_type":"","tags":[],"related":[],"keywords":[]}},"caveats":"","business_terms":[{{"name":"","definition":""}}]}}"""


def _compute_confidence(
    summary: dict[str, str],
    fields: list[SchemaField],
    table: SchemaTable,
) -> str:
    """根据存储过程命中数、字段备注覆盖率、表备注自动评估置信度。"""
    routine_count = len(summary.get("routine_evidence", []))
    field_with_comment = sum(
        1 for f in fields if f.original_comment or f.supplementary_comment
    )
    has_table_comment = bool(table.original_comment or table.supplementary_comment)
    total_fields = max(len(fields), 1)

    score = 0
    if routine_count >= 2:
        score += 3
    elif routine_count >= 1:
        score += 1

    if field_with_comment / total_fields > 0.5:
        score += 3
    elif field_with_comment > 0:
        score += 1

    if has_table_comment:
        score += 2

    if score >= 5:
        return "high"
    elif score >= 2:
        return "medium"
    return "low"


def build_note_properties(
    datasource: DataSource,
    table: SchemaTable,
    summary: dict[str, str],
    generated_at: datetime,
    *,
    fields: list[SchemaField] | None = None,
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

    # ── 新增 LLM Wiki 质量字段 ──
    note_properties.setdefault(
        "source",
        "ai-generated" if summary.get("_source") == "ai" else "rules-generated",
    )
    if fields is not None:
        note_properties.setdefault(
            "confidence", _compute_confidence(summary, fields, table)
        )
    else:
        note_properties.setdefault("confidence", "medium")
    # contested 由人工手动添加，同步过程不自动设置
    note_properties.setdefault("contested", False)

    # ── 新增溯源字段 ──
    # source_tables：此页内容依赖哪些表（从 graph_links + routine_evidence 反推）
    routine_evidence = summary.get("routine_evidence", [])
    source_routine_names: list[str] = []
    for item in routine_evidence:
        rname = f"{item.get('owner', '')}.{item.get('name', '')}"
        if rname not in source_routine_names:
            source_routine_names.append(rname)
    note_properties.setdefault("source_routines", source_routine_names)
    # source_tables：从 graph_links 提取的目标表 + 当前表自身
    source_table_names: list[str] = [table.name]
    for gl in summary.get("graph_links", []) or []:
        target = gl.get("target_table", "")
        if target and target not in source_table_names:
            source_table_names.append(target)
    note_properties.setdefault("source_tables", source_table_names)
    # review_status：AI 生成的内容默认 unreviewed
    note_properties.setdefault("review_status", "unreviewed")

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

    # 1. 优先按换行符拆分
    if "\n" in normalized:
        items = [line.strip(" -*•") for line in normalized.splitlines() if line.strip()]
        return [f"- {item}" for item in items] or ["- 暂无"]

    # 2. 尝试按分号拆分（处理挤在一起的情况）
    if ";" in normalized or "；" in normalized:
        items = [item.strip() for item in re.split(r"[;；]", normalized) if item.strip()]
        if len(items) > 1:
            return [f"- {item}" for item in items]

    # 3. 尝试按数字列表拆分 (1. 2. 3. 或 1、 2、 3、)
    numbered = re.split(r"\s*(?:\d+[\.、]\s*)", normalized)
    numbered_items = [item.strip() for item in numbered if item.strip()]
    if len(numbered_items) > 1:
        return [f"- {item}" for item in numbered_items]

    # 4. 尝试按句号拆分（如果包含多个冒号，通常是 字段: 说明 格式）
    sentences = [item.strip() for item in re.split(r"(?<=。)", normalized) if item.strip()]
    colon_count = normalized.count("：") + normalized.count(":")
    if colon_count >= 2 and len(sentences) > 1:
        return [f"- {item}" for item in sentences]

    return [normalized]


# ── LLM Wiki 人工页面保护辅助 ──

def _read_frontmatter(file_path: Path) -> dict[str, str]:
    """读取 markdown 文件的 YAML frontmatter（仅前 50 行）。"""
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fm: dict[str, str] = {}
    for line in lines[1:50]:
        stripped = line.strip()
        if stripped == "---":
            break
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            fm[key.strip()] = val.strip()
    return fm


def _extract_manual_sections(file_path: Path) -> list[str]:
    """提取人工标记的段落（## 手动备注）。"""
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError:
        return []
    sections: list[str] = []
    in_manual = False
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("## 手动备注"):
            in_manual = True
            buf = [line]
            continue
        if in_manual:
            if line.startswith("## ") and not line.startswith("## 手动备注"):
                sections.append("\n".join(buf))
                in_manual = False
                buf = []
            else:
                buf.append(line)
    if in_manual and buf:
        sections.append("\n".join(buf))
    return sections


def _merge_hybrid_content(ai_markdown: str, manual_sections: list[str]) -> str:
    """将人工备注段落追加到 AI 生成的 markdown 末尾。"""
    if not manual_sections:
        return ai_markdown
    return ai_markdown.rstrip() + "\n\n" + "\n\n".join(manual_sections) + "\n"
