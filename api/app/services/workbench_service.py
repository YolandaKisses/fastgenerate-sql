from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Optional

from sqlmodel import Session, select

from app.core.config import settings
from app.models.datasource import DataSource, DataSourceStatus
from app.models.schema import SchemaField, SchemaTable
from app.services.hermes_service import iter_hermes_session_json, run_hermes_session_json
from app.services import setting_service
from app.services.rag import retriever
from app.services.rag.schemas import RetrievalItem, SearchResult
from app.services.rag.schemas import RetrievalItem, SearchResult
from app.services.sql_prompt_builder import build_sql_prompt, WIKI_AGENT_SYSTEM_PROMPT


MAX_NOTE_CHARS = 4000
OPTION_PATTERN = re.compile(r"^[A-Za-z0-9]$")
WRITE_SQL_PATTERN = re.compile(r"\b(insert|update|delete|drop|alter|truncate|create|replace)\b", re.I)
FOOD_GUESS_PATTERN = re.compile(r"(外卖|餐饮|美食)")
USER_INTENT_PATTERN = re.compile(r"(用户|人员|成员|账号|账户)")
USER_LIST_PATTERN = re.compile(r"(哪些用户|用户清单|用户列表|存在哪些用户|有哪些用户)")


def normalize_note_name(name: str) -> str:
    return Path(name).stem


def note_used_payload(note_name: str) -> dict[str, str]:
    return {"note": normalize_note_name(note_name), "comment": ""}


def clean_obsidian_note_text(text: str) -> str:
    lines = text.splitlines()
    cleaned: list[str] = []
    skip = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## 概述") or stripped.startswith("## 字段明细"):
            skip = True
            continue
        if skip and stripped.startswith("## "):
            skip = False
        if skip:
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def _truncate_note_text(text: str, max_chars: int = MAX_NOTE_CHARS) -> str:
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    if "\n" in truncated:
        truncated = truncated.rsplit("\n", 1)[0]
    return truncated.rstrip() + "\n（后续内容已裁剪）"


def read_relevant_table_notes(
    candidates: list[dict[str, Any]],
    notes_dir: str | Path,
) -> tuple[str, list[str]]:
    root = Path(notes_dir)
    note_chunks: list[str] = []
    used_notes: list[str] = []
    for item in candidates:
        table: SchemaTable = item["table"]
        note_path = root / f"{table.name}.md"
        if not note_path.exists():
            continue
        content = _truncate_note_text(clean_obsidian_note_text(note_path.read_text(encoding="utf-8")))
        note_chunks.append(f"### {table.name}.md\n{content}")
        used_notes.append(table.name)
    return "\n\n".join(note_chunks), used_notes


def build_schema_retrieval_question(question: str, history: list[dict[str, str]] | None = None) -> str:
    history = history or []
    if not OPTION_PATTERN.match(question.strip()):
        recent_users = [item["content"] for item in history if item.get("role") == "user"][-4:]
        return "\n".join(recent_users + [question]) if recent_users else question

    recent_users = [item["content"] for item in history if item.get("role") == "user"][-4:]
    assistant_clarification = ""
    for item in reversed(history):
        if item.get("role") == "assistant" and "请选择" in item.get("content", ""):
            assistant_clarification = item["content"]
            break
    parts = recent_users
    if assistant_clarification:
        parts.append(assistant_clarification)
    parts.append(question)
    return "\n".join(parts)


def should_allow_schema_fallback(
    question: str,
    history: list[dict[str, str]] | None = None,
    hermes_session_id: str | None = None,
) -> bool:
    if OPTION_PATTERN.match(question.strip()) and history and hermes_session_id:
        return False
    return True


def should_resume_hermes_session(
    question: str,
    history: list[dict[str, str]] | None = None,
    hermes_session_id: str | None = None,
) -> bool:
    if not hermes_session_id:
        return False
    # 只要前端传了 session_id，就优先尝试在原有会话中继续，以支持多轮对话
    return True


def can_ask_datasource(datasource: DataSource) -> bool:
    return datasource.status == DataSourceStatus.CONNECTION_OK


def _tokenize(text: str) -> list[str]:
    lowered = text.lower()
    latin = re.findall(r"[a-z0-9_]+", lowered)
    cjk = re.findall(r"[\u4e00-\u9fff]{1,}", lowered)
    return latin + cjk


def _field_synonyms(field: SchemaField) -> list[str]:
    values = [field.name, field.original_comment or "", field.supplementary_comment or ""]
    tokens: list[str] = []
    for value in values:
        tokens.extend(_tokenize(value))
    return tokens


def _table_synonyms(table: SchemaTable) -> list[str]:
    values = [table.name, table.original_comment or "", table.supplementary_comment or ""]
    tokens: list[str] = []
    for value in values:
        tokens.extend(_tokenize(value))
    return tokens


def _is_user_like_table(table_name: str) -> bool:
    normalized = table_name.lower()
    return any(token in normalized for token in ["user", "member", "account", "investor", "person"])


def _user_intent_bonus(question: str, table: SchemaTable, table_fields: list[SchemaField]) -> float:
    if not USER_INTENT_PATTERN.search(question):
        return 0.0
    bonus = 0.0
    table_name = table.name.lower()
    if _is_user_like_table(table_name):
        bonus += 5.0
    if table_name.startswith("sys_user") or table_name == "sys_user":
        bonus += 6.0
    if table_name.endswith("_user") or table_name.endswith("_users") or table_name == "demo_users":
        bonus += 4.0

    user_field_hints = {
        "user_id",
        "userid",
        "f_userid",
        "username",
        "vc_username",
        "userno",
        "vc_userno",
        "account",
        "vc_account",
        "loginname",
        "vc_loginname",
        "nickname",
        "vc_nickname",
        "name",
    }
    matched_fields = 0
    for field in table_fields:
        field_name = field.name.lower()
        field_comment = f"{field.original_comment or ''} {field.supplementary_comment or ''}".lower()
        if field_name in user_field_hints:
            matched_fields += 1
            bonus += 2.2
        elif any(hint in field_name for hint in ["user", "account", "login", "name", "nick"]):
            bonus += 1.1
        if any(term in field_comment for term in ["用户", "姓名", "账号", "账户", "登录", "昵称"]):
            bonus += 1.0
    if USER_LIST_PATTERN.search(question) and matched_fields >= 2:
        bonus += 3.0
    return bonus


def retrieve_relevant_schema(
    session: Session,
    datasource_id: int,
    question: str,
    allow_fallback: bool = True,
) -> list[dict[str, Any]]:
    if not allow_fallback and re.search(r"\n[A-Za-z]$", question.strip()):
        return []

    datasource = session.get(DataSource, datasource_id)
    if not datasource or datasource.status == DataSourceStatus.CONNECTION_FAILED:
        return []

    tables = session.exec(select(SchemaTable).where(SchemaTable.datasource_id == datasource_id)).all()
    fields = session.exec(select(SchemaField)).all()
    field_map: dict[int, list[SchemaField]] = {}
    for field in fields:
        field_map.setdefault(field.table_id, []).append(field)

    query_tokens = set(_tokenize(question))
    candidates: list[tuple[float, dict[str, Any]]] = []
    for table in tables:
        table_fields = field_map.get(table.id or -1, [])
        score = 0.0
        table_tokens = set(_table_synonyms(table))
        for token in query_tokens:
            if token in table_tokens:
                score += 4.0
        for field in table_fields:
            field_tokens = set(_field_synonyms(field))
            for token in query_tokens:
                if token in field_tokens:
                    score += 2.5
        if table.name.lower() in question.lower():
            score += 6.0
        score += _user_intent_bonus(question, table, table_fields)
        if score > 0:
            candidates.append((score, {"table": table, "fields": table_fields}))

    candidates.sort(key=lambda item: (item[0], item[1]["table"].name), reverse=True)
    return [item for _, item in candidates[:6]]


def validate_sql_candidate(sql: str) -> dict[str, Any]:
    reasons: list[str] = []
    statements = [segment.strip() for segment in sql.split(";") if segment.strip()]
    if len(statements) > 1:
        reasons.append("禁止执行多条语句")
    if WRITE_SQL_PATTERN.search(sql):
        reasons.append("仅允许生成只读 SELECT SQL")
    return {"status": "invalid" if reasons else "valid", "reasons": reasons}


def validate_sql_against_schema(sql: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []
    tables = {item["table"].name: item["table"] for item in candidates}
    fields_by_table = {
        item["table"].name: {field.name for field in item["fields"]}
        for item in candidates
    }
    for table_name, field_name in re.findall(r"([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)", sql):
        if table_name not in fields_by_table:
            warnings.append(f"SQL 中引用了未纳入上下文的表: {table_name}")
            continue
        if field_name not in fields_by_table[table_name]:
            reasons.append(f"字段 {table_name}.{field_name} 在当前 schema 中不存在的字段")
    return {"status": "invalid" if reasons else "valid", "reasons": reasons, "warnings": warnings}


def _build_schema_context(candidates: list[dict[str, Any]]) -> str:
    lines = ["### Schema Context", "以下内容是唯一可信的表字段来源：", ""]
    for item in candidates:
        table: SchemaTable = item["table"]
        lines.append(f"表: {table.name}")
        if table.original_comment:
            lines.append(f"备注: {table.original_comment}")
        if table.supplementary_comment:
            lines.append(f"补充: {table.supplementary_comment}")
        for field in item["fields"]:
            comment = field.original_comment or field.supplementary_comment or ""
            lines.append(f"- {field.name} ({field.type}) {comment}".rstrip())
        lines.append("")
    return "\n".join(lines).strip()


def _wiki_search_result(
    *,
    session: Session,
    datasource: DataSource,
    question: str,
    top_k: int = 8,
) -> SearchResult:
    wiki_root = _wiki_root(session)
    direct = retriever.direct_lookup(
        query=question,
        wiki_root=wiki_root,
        filters={"datasource": datasource.name},
        top_k=top_k,
    )
    if direct is not None:
        return direct
    return retriever.search(
        query=question,
        wiki_root=wiki_root,
        filters={"datasource": datasource.name},
        top_k=top_k,
    )


def _parse_schema_fields_from_markdown(content: str) -> list[SchemaField]:
    fields: list[SchemaField] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if "字段名" in stripped or "---" in stripped or ":---" in stripped:
            continue
        parts = [part.strip().strip("*`") for part in stripped.strip("|").split("|")]
        if len(parts) < 2:
            continue
        field_name = parts[0].strip()
        field_type = parts[1].strip()
        if not field_name or not field_type:
            continue
        comment = parts[2].strip() if len(parts) > 2 else ""
        supplementary = parts[3].strip() if len(parts) > 3 else ""
        fields.append(
            SchemaField(
                table_id=-1,
                name=field_name,
                type=field_type,
                original_comment=comment or None,
                supplementary_comment=supplementary or None,
            )
        )
    return fields


def _obsidian_tables_dir(session: Session, datasource_name: str) -> Path:
    root = setting_service.get_setting(session, "obsidian_vault_root")
    if not root:
        return Path(".")
    return Path(root) / datasource_name / "tables"


def _wiki_root(session: Session) -> Path:
    return Path(setting_service.get_setting(session, "wiki_root", settings.WIKI_ROOT))


def _parse_schema_candidates_from_search_result(
    *,
    session: Session,
    datasource: DataSource,
    search_result: SearchResult,
) -> list[dict[str, Any]]:
    wiki_root = _wiki_root(session)
    candidates: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for item in search_result.items:
        if item.source_type != "schema":
            continue
        table_name = item.object_name or item.title
        if not table_name or table_name in seen_names:
            continue
        file_path = wiki_root / item.path
        if not file_path.exists():
            continue
        content = file_path.read_text(encoding="utf-8")
        fields = _parse_schema_fields_from_markdown(content)
        if not fields:
            continue
        table = SchemaTable(
            datasource_id=datasource.id or 0,
            name=table_name,
            original_comment=item.snippet[:120] if item.snippet else None,
            supplementary_comment="来自本地 Wiki 结构化文档",
        )
        candidates.append({"table": table, "fields": fields})
        seen_names.add(table_name)
    return candidates


def _knowledge_schema_candidates(
    session: Session,
    datasource: DataSource,
    question: str,
) -> list[dict[str, Any]]:
    result = _wiki_search_result(session=session, datasource=datasource, question=question, top_k=8)
    candidates = _parse_schema_candidates_from_search_result(
        session=session,
        datasource=datasource,
        search_result=result,
    )
    scored: list[dict[str, Any]] = []
    for item in candidates:
        table = item["table"]
        fields = item["fields"]
        scored.append(
            {
                **item,
                "_score": _user_intent_bonus(question, table, fields)
                + (6.0 if _is_user_like_table(table.name) else 0.0)
                + len(fields) * 0.05,
            }
        )
    scored.sort(key=lambda item: (item.get("_score", 0), item["table"].name), reverse=True)
    for item in scored:
        item.pop("_score", None)
    return scored


def _merge_schema_candidates(
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged = list(primary)
    existing = {item["table"].name for item in primary}
    for item in secondary:
        table_name = item["table"].name
        if table_name in existing:
            continue
        merged.append(item)
        existing.add(table_name)
    merged.sort(
        key=lambda item: (
            1 if item["table"].name.lower().startswith("sys_user") else 0,
            1 if _is_user_like_table(item["table"].name) else 0,
            len(item.get("fields", [])),
            item["table"].name,
        ),
        reverse=True,
    )
    return merged


def _build_retrieval_context(
    *,
    search_result: SearchResult,
    top_k: int = 5,
) -> str:
    if not search_result.items:
        return ""
    lines = ["### Knowledge Evidence"]
    for item in search_result.items[:top_k]:
        lines.append(f"- {item.title} [{item.source_type}] ({item.path})")
        lines.append(f"  片段: {item.snippet}")
    return "\n".join(lines)


def _build_relation_context_from_hits(items: list[RetrievalItem], top_k: int = 4) -> str:
    relation_items = [item for item in items if item.source_type in {"lineage", "demand", "schema"}]
    if not relation_items:
        return ""
    lines = ["### Relation Context"]
    for item in relation_items[:top_k]:
        lines.append(f"- {item.title} [{item.source_type}]")
        lines.append(f"  关联线索: {item.snippet}")
    return "\n".join(lines)


def _build_prompt(
    *,
    session: Session,
    datasource: DataSource,
    question: str,
    candidates: list[dict[str, Any]],
    search_result: SearchResult,
    correction_hint: str | None = None,
) -> tuple[str, list[str]]:
    schema_context = _build_schema_context(candidates) if candidates else "### Schema Context\n当前没有命中的 schema 上下文。"
    notes_text, used_notes = read_relevant_table_notes(candidates, _obsidian_tables_dir(session, datasource.name))
    retrieval_text = _build_retrieval_context(search_result=search_result)
    relation_text = _build_relation_context_from_hits(search_result.items)
    if not relation_text and candidates:
        relation_lines = ["### Relation Context"]
        for item in candidates:
            table: SchemaTable = item["table"]
            if table.related_tables:
                relation_lines.append(f"- {table.name}: {table.related_tables}")
        if len(relation_lines) > 1:
            relation_text = "\n".join(relation_lines)

    inferred_hint = ""
    if candidates:
        top_table = candidates[0]["table"].name
        if USER_INTENT_PATTERN.search(question) and _is_user_like_table(top_table):
            inferred_hint = f"若问题是在查询用户/人员清单，优先基于候选表 {top_table} 生成 SQL；只有在字段明显不足时才返回 clarification。"
    merged_correction = "\n".join([part for part in [correction_hint or "", inferred_hint] if part.strip()])

    prompt = build_sql_prompt(
        schema_context=schema_context,
        structured_knowledge_context=notes_text,
        business_evidence=retrieval_text.replace("### Knowledge Evidence\n", "") if retrieval_text else "",
        relation_context=relation_text.replace("### Relation Context\n", "") if relation_text else "",
        correction_hint=merged_correction,
        question=question,
    )
    return prompt, used_notes


def _extract_missing_schema_hint(result: dict[str, Any], candidates: list[dict[str, Any]]) -> str | None:
    if result.get("type") != "clarification":
        return None
    message = str(result.get("message") or "")
    table_names = [item["table"].name for item in candidates]
    mentioned = [name for name in table_names if name in message]
    if "schema" in message.lower() or "可用表" in message:
        if mentioned:
            return f"候选 schema 中已经包含以下表，请基于这些表重新判断：{', '.join(mentioned)}。不要错误声称这些表缺失。"
    return None


def ask_llm(
    session: Session,
    datasource_id: int,
    question: str,
    history: list[dict[str, str]] | None = None,
    hermes_session_id: str | None = None,
) -> dict[str, Any]:
    datasource = session.get(DataSource, datasource_id)
    if not datasource:
        return {"type": "error", "message": "数据源不存在"}

    wiki_root = _wiki_root(session)
    resumed_session_id = (
        hermes_session_id
        if should_resume_hermes_session(question, history, hermes_session_id)
        else None
    )

    # 1. 组装简化的 Prompt，直接发给 Hermes
    system_prompt = WIKI_AGENT_SYSTEM_PROMPT.format(
        wiki_root=wiki_root,
        db_type=datasource.db_type,
        datasource_name=datasource.name
    )
    prompt = f"{system_prompt}\n\n### 用户问题\n{question}"

    result, session_id = run_hermes_session_json(prompt, session_id=resumed_session_id)

    # 2. 基础 SQL 安全校验
    if result.get("type") == "sql_candidate":
        candidate_validation = validate_sql_candidate(result.get("sql", ""))
        if candidate_validation["status"] != "valid":
            return {"type": "error", "message": "；".join(candidate_validation["reasons"])}
    
    result["session_id"] = session_id
    return result


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _needs_guess_clarification(result: dict[str, Any]) -> bool:
    if result.get("type") != "sql_candidate":
        return False
    sql = str(result.get("sql") or "")
    explanation = str(result.get("explanation") or "")
    return "product_name" in sql and FOOD_GUESS_PATTERN.search(sql + explanation) is not None


def ask_llm_stream(
    session: Session,
    datasource_id: int,
    question: str,
    history: list[dict[str, str]] | None = None,
    hermes_session_id: str | None = None,
) -> Generator[str, None, None]:
    datasource = session.get(DataSource, datasource_id)
    if not datasource:
        yield _sse("error", {"message": "数据源不存在"})
        return

    wiki_root = _wiki_root(session)
    resumed_session_id = (
        hermes_session_id
        if should_resume_hermes_session(question, history, hermes_session_id)
        else None
    )

    # 1. 组装简化的 Prompt，直接发给 Hermes
    system_prompt = WIKI_AGENT_SYSTEM_PROMPT.format(
        wiki_root=wiki_root,
        db_type=datasource.db_type,
        datasource_name=datasource.name
    )
    prompt = f"{system_prompt}\n\n### 用户问题\n{question}"

    # 如果是继续会话，立即下发已知 ID；如果是新会话，逻辑会在 iter_hermes_session_json 内部第一时间返回分配的 ID
    if resumed_session_id:
        yield _sse("session_id", {"session_id": resumed_session_id})

    for event in iter_hermes_session_json(prompt, session_id=resumed_session_id):
        # 捕获从 hermes_service 传回的初始 session_id 事件
        if event.get("type") == "session_id":
            yield _sse("session_id", {"session_id": event["session_id"]})
            continue

        if event["type"] == "trace":
            yield _sse("hermes_trace", {"message": event["message"]})
            continue
        result = event["result"]
        session_id = event.get("session_id")

        # 针对 Wiki Agent 模式，如果 result 包含多条候选，自动处理成前端可用的格式
        if result.get("type") == "sql_candidate" and not result.get("sql"):
            candidates = result.get("candidates") or result.get("sql_candidates")
            if candidates and isinstance(candidates, list) and len(candidates) > 0:
                # 默认取第一条作为主 SQL 兼容旧逻辑
                result["sql"] = candidates[0].get("sql")
                result["explanation"] = candidates[0].get("explanation") or result.get("explanation")

        # 处理可能的召回提示
        for note in result.get("used_notes", []):
            yield _sse("note_used", note_used_payload(note))
            
        payload = dict(result)
        if session_id:
            payload["session_id"] = session_id
        yield _sse("result", payload)
        return
