import json
import re
from pathlib import Path
from sqlmodel import Session, select
from app.models.datasource import DataSource, DataSourceStatus
from app.models.schema import SchemaTable, SchemaField
from app.models.audit_log import AuditLog
import sqlalchemy
import time
from app.services.datasource_service import build_database_url
from app.core.config import settings
from app.services.hermes_service import run_hermes_json
STOP_WORDS = {"查询", "多少", "什么", "哪些", "怎么", "一下", "数据", "统计", "上周", "本周", "昨天", "今天", "最近"}
ALLOWED_RESPONSE_TYPES = {"clarification", "sql_candidate"}


def commit_with_warning(session: Session, warning_message: str) -> str | None:
    try:
        session.commit()
        return None
    except Exception:
        session.rollback()
        return warning_message

def tokenize_question(question: str) -> list[str]:
    tokens = set()
    parts = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", question.lower())
    for part in parts:
        if part not in STOP_WORDS:
            tokens.add(part)
        if re.fullmatch(r"[\u4e00-\u9fff]+", part):
            for size in range(2, min(5, len(part) + 1)):
                for idx in range(0, len(part) - size + 1):
                    token = part[idx:idx + size]
                    if token not in STOP_WORDS:
                        tokens.add(token)
    return sorted(tokens, key=len, reverse=True)


def collect_table_payload(session: Session, datasource_id: int) -> list[dict]:
    tables = session.exec(select(SchemaTable).where(SchemaTable.datasource_id == datasource_id)).all()
    payload = []
    for table in tables:
        fields = session.exec(select(SchemaField).where(SchemaField.table_id == table.id)).all()
        payload.append({"table": table, "fields": fields})
    return payload


def sanitize_path_segment(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]+', "-", value).strip()
    return cleaned or "untitled"


def get_datasource_knowledge_dir(datasource_name: str) -> Path:
    return Path(settings.OBSIDIAN_VAULT_ROOT) / sanitize_path_segment(datasource_name) / "tables"


def retrieve_relevant_schema(session: Session, datasource_id: int, question: str, limit: int = 6) -> list[dict]:
    tokens = tokenize_question(question)
    payload = collect_table_payload(session, datasource_id)
    if not payload:
        return []

    ranked = []
    for item in payload:
        table = item["table"]
        fields = item["fields"]
        haystacks = [
            table.name.lower(),
            (table.original_comment or "").lower(),
            (table.supplementary_comment or "").lower(),
        ]
        for field in fields:
            haystacks.extend(
                [
                    field.name.lower(),
                    (field.original_comment or "").lower(),
                    (field.supplementary_comment or "").lower(),
                ]
            )

        score = 0
        matched_terms = set()
        for token in tokens:
            for haystack in haystacks:
                if token and token in haystack:
                    score += 2 if haystack == table.name.lower() else 1
                    matched_terms.add(token)
                    break

        if score > 0:
            ranked.append({"score": score, "matched_terms": matched_terms, **item})

    if not ranked:
        return payload[: min(limit, len(payload))]

    ranked.sort(key=lambda item: (item["score"], len(item["matched_terms"])), reverse=True)
    return ranked[:limit]


def detect_ambiguity(question: str, candidates: list[dict]) -> str | None:
    if len(candidates) < 2:
        return None

    token_hits = {}
    for candidate in candidates:
        matched_terms = candidate.get("matched_terms", set())
        for term in matched_terms:
            token_hits[term] = token_hits.get(term, 0) + 1

    ambiguous_terms = [term for term, count in token_hits.items() if count > 1]
    if ambiguous_terms and len(question.strip()) <= 20:
        term = sorted(ambiguous_terms, key=len, reverse=True)[0]
        return f"你提到的“{term}”可能对应多个表或字段。请补充你要看的是哪类业务对象、时间范围或统计口径。"

    top_score = candidates[0].get("score", 0)
    second_score = candidates[1].get("score", 0)
    if top_score == second_score and top_score > 0 and len(question.strip()) <= 12:
        return "当前问题可能命中多个表。请补充具体业务对象、时间范围或你想统计的指标。"

    return None


def build_schema_context(candidates: list[dict]) -> str:
    """构建 Schema 上下文，供 LLM prompt 使用"""
    tables = candidates or []
    if not tables:
        return "（该数据源暂无同步的表结构）"

    lines = []
    for item in tables:
        t = item["table"]
        comment_parts = []
        if t.original_comment:
            comment_parts.append(t.original_comment)
        if t.supplementary_comment:
            comment_parts.append(f"[补充: {t.supplementary_comment}]")
        comment = " ".join(comment_parts) if comment_parts else ""
        lines.append(f"\n### 表: {t.name}  {comment}")

        for f in item["fields"]:
            f_comment_parts = []
            if f.original_comment:
                f_comment_parts.append(f.original_comment)
            if f.supplementary_comment:
                f_comment_parts.append(f"[补充: {f.supplementary_comment}]")
            f_comment = " ".join(f_comment_parts) if f_comment_parts else ""
            lines.append(f"  - {f.name} ({f.type}) {f_comment}")

    return "\n".join(lines)


def validate_llm_result(result: dict) -> dict:
    result_type = result.get("type")
    if result_type not in ALLOWED_RESPONSE_TYPES:
        raise ValueError("LLM 返回了不支持的结果类型")
    if result_type == "clarification" and not result.get("message"):
        raise ValueError("LLM 返回澄清结果但缺少 message")
    if result_type == "sql_candidate" and not result.get("sql"):
        raise ValueError("LLM 返回 SQL 候选但缺少 sql")
    return result


def normalize_sql(sql: str) -> str:
    no_block_comments = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    no_line_comments = re.sub(r"--.*?$", " ", no_block_comments, flags=re.M)
    collapsed = re.sub(r"\s+", " ", no_line_comments).strip()
    # 移除末尾的分号，方便后续判断是否为多条语句
    return collapsed.rstrip(";")


def validate_sql_candidate(sql: str) -> dict:
    normalized_sql = normalize_sql(sql)
    if not normalized_sql:
        return {"status": "invalid", "normalized_sql": normalized_sql, "reasons": ["SQL 为空"]}

    sql_upper = normalized_sql.upper()
    reasons = []
    # 如果剥离末尾分号后依然包含分号，说明存在多条语句
    if ";" in normalized_sql:
        reasons.append("禁止执行多条语句")

    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE", "CALL", "EXEC"]
    for keyword in forbidden:
        if sql_upper.startswith(keyword) or f" {keyword} " in sql_upper:
            reasons.append(f"禁止执行包含 {keyword} 的语句")
            break

    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        reasons.append("仅允许 SELECT 或 WITH 开头的只读查询")

    return {
        "status": "invalid" if reasons else "valid",
        "normalized_sql": normalized_sql,
        "reasons": reasons,
    }

def ask_llm(session: Session, datasource_id: int, question: str) -> dict:
    """核心问答：优先让 Hermes 检索 Obsidian 知识库 -> 返回澄清或 SQL"""
    ds = session.get(DataSource, datasource_id)
    if not ds:
        return {"type": "error", "message": "数据源不存在"}

    if ds.status not in (DataSourceStatus.READY, DataSourceStatus.CONNECTION_OK):
        return {"type": "error", "message": f"数据源状态为 {ds.status}，请先完成连接测试"}

    knowledge_dir = get_datasource_knowledge_dir(ds.name)
    if not knowledge_dir.exists():
        return {"type": "error", "message": "当前数据源还没有可用知识库，请先完成同步到知识库后再问答"}

    candidates = retrieve_relevant_schema(session, datasource_id, question)
    ambiguity_message = detect_ambiguity(question, candidates)
    if ambiguity_message:
        log = AuditLog(
            datasource_id=datasource_id,
            datasource_name=ds.name,
            question=question,
            clarified=True,
            clarification_content=ambiguity_message,
            executed=False
        )
        session.add(log)
        warning = commit_with_warning(session, "问答已返回澄清，但审计日志写入失败")
        payload = {"type": "clarification", "message": ambiguity_message}
        if warning:
            payload["warning"] = warning
        return payload

    system_prompt = f"""你是一个企业级 SQL 生成助手。你当前的任务是先去本地 Obsidian 知识库里检索当前数据源相关笔记，再根据检索结果生成只读 SQL 或提出澄清问题。

规则：
1. 只能生成 SELECT 语句，严禁生成 INSERT / UPDATE / DELETE / DROP / ALTER 等写操作。
2. 如果用户的问题不够清晰，先澄清，不要猜测。
3. 数据库类型为 {ds.db_type}，请使用对应方言。
4. 你的主要知识来源是 Obsidian 知识库，不是直接使用内嵌 Schema。
5. 请先在下面目录中查找与问题最相关的表笔记，再决定 SQL：
   {knowledge_dir}
6. 可以阅读命中的表笔记 frontmatter、用途说明、核心字段解读、关联笔记、字段明细。
7. 如果需要，可继续顺着 related/wiki link 读取少量关联笔记，但不要无关泛读。
8. 返回 JSON 格式，只允许以下两种：
   - 澄清：{{"type": "clarification", "message": "你的澄清问题"}}
   - SQL：{{"type": "sql_candidate", "sql": "SELECT ...", "explanation": "这条 SQL 的含义"}}
9. 不要返回任何其他格式。
"""

    try:
        prompt = f"""{system_prompt}

用户问题：{question}

执行要求：
1. 先检索并阅读当前数据源知识库中的相关笔记。
2. 优先根据笔记属性、用途说明、核心字段解读、关联笔记和字段明细来判断要查询哪些表。
3. 如果多个表都可能相关，请先澄清，而不是盲目生成 SQL。
4. 如果知识库中找不到足够信息，也请先澄清，不要编造字段。
5. 请严格只返回 JSON。"""
        result = validate_llm_result(run_hermes_json(prompt, cwd=str(knowledge_dir)))

        # 记录审计日志
        log = AuditLog(
            datasource_id=datasource_id,
            datasource_name=ds.name,
            question=question,
            clarified=result.get("type") == "clarification",
            clarification_content=result.get("message") if result.get("type") == "clarification" else None,
            sql=result.get("sql"),
            executed=False
        )
        session.add(log)
        warning = commit_with_warning(session, "问答成功，但审计日志写入失败")
        if warning:
            result["warning"] = warning
        return result
    except ValueError as e:
        return {"type": "error", "message": str(e)}
    except Exception as e:
        return {"type": "error", "message": str(e)}


def apply_query_limits(conn, db_type: str, timeout_ms: int = 30000):
    raw_connection = getattr(getattr(conn, "connection", None), "driver_connection", None)
    if raw_connection is not None and hasattr(raw_connection, "call_timeout"):
        raw_connection.call_timeout = timeout_ms

    if db_type == "mysql":
        conn.execute(sqlalchemy.text(f"SET SESSION MAX_EXECUTION_TIME={timeout_ms}"))
    elif db_type == "postgresql":
        conn.execute(sqlalchemy.text(f"SET statement_timeout = {timeout_ms}"))

def execute_readonly_sql(session: Session, datasource_id: int, sql: str) -> dict:
    """校验并执行只读 SQL"""
    ds = session.get(DataSource, datasource_id)
    if not ds:
        return {"status": "error", "message": "数据源不存在"}

    # 只读校验
    normalized_sql = normalize_sql(sql)
    validation = validate_sql_candidate(sql)
    if validation["status"] == "invalid":
        return {"status": "error", "message": "；".join(validation["reasons"])}

    try:
        url = build_database_url(ds)
        engine = sqlalchemy.create_engine(url)

        start_time = time.time()
        with engine.connect() as conn:
            apply_query_limits(conn, ds.db_type, 30000)
            result = conn.execute(sqlalchemy.text(sql))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchmany(500)]
            duration_ms = int((time.time() - start_time) * 1000)

        # 更新审计日志
        log = session.exec(
            select(AuditLog)
            .where(AuditLog.datasource_id == datasource_id, AuditLog.sql == sql)
            .order_by(AuditLog.created_at.desc())
        ).first()

        if log:
            log.executed = True
            log.execution_status = "success" if rows else "empty"
            log.duration_ms = duration_ms
            log.row_count = len(rows)
            session.add(log)
            warning = commit_with_warning(session, "查询成功，但审计日志写入失败")
        else:
            warning = None

        # 查找字段中文备注
        column_comments = {}
        tables = session.exec(select(SchemaTable).where(SchemaTable.datasource_id == datasource_id)).all()
        for t in tables:
            fields = session.exec(select(SchemaField).where(SchemaField.table_id == t.id)).all()
            for f in fields:
                # 优先使用补充备注，其次使用原始备注
                comment = f.supplementary_comment or f.original_comment or f.name
                column_comments[f.name] = comment

        result_payload = {
            "status": "success" if rows else "empty",
            "columns": columns,
            "column_comments": column_comments,
            "rows": rows,
            "row_count": len(rows),
            "duration_ms": duration_ms
        }
        if warning:
            result_payload["warning"] = warning
        return result_payload
    except Exception as e:
        # 更新审计日志
        log = session.exec(
            select(AuditLog)
            .where(AuditLog.datasource_id == datasource_id, AuditLog.sql == sql)
            .order_by(AuditLog.created_at.desc())
        ).first()
        if log:
            log.executed = True
            log.execution_status = "error"
            log.error_summary = str(e)[:500]
            session.add(log)
            warning = commit_with_warning(session, "SQL 执行失败，同时审计日志写入失败")
        else:
            warning = None

        payload = {"status": "error", "message": str(e)}
        if warning:
            payload["warning"] = warning
        return payload
