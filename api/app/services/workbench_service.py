import json
import re
import httpx
from sqlmodel import Session, select
from app.models.model_config import ModelConfig
from app.models.datasource import DataSource, DataSourceStatus
from app.models.schema import SchemaTable, SchemaField
from app.models.audit_log import AuditLog
import sqlalchemy
import time
from app.services.datasource_service import build_database_url

STOP_WORDS = {"查询", "多少", "什么", "哪些", "怎么", "一下", "数据", "统计", "上周", "本周", "昨天", "今天", "最近"}
ALLOWED_RESPONSE_TYPES = {"clarification", "sql_candidate"}


def get_or_create_config(session: Session) -> ModelConfig:
    config = session.exec(select(ModelConfig)).first()
    if not config:
        config = ModelConfig()
        session.add(config)
        session.commit()
        session.refresh(config)
    return config

def save_config(session: Session, data: dict) -> ModelConfig:
    config = get_or_create_config(session)
    for key, value in data.items():
        if hasattr(config, key) and value is not None:
            setattr(config, key, value)
    session.add(config)
    session.commit()
    session.refresh(config)
    return config

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

def ask_llm(session: Session, datasource_id: int, question: str) -> dict:
    """核心问答：召回 Schema -> 构建 prompt -> 调 LLM -> 返回结果"""
    ds = session.get(DataSource, datasource_id)
    if not ds:
        return {"type": "error", "message": "数据源不存在"}

    if ds.status not in (DataSourceStatus.READY, DataSourceStatus.CONNECTION_OK):
        return {"type": "error", "message": f"数据源状态为 {ds.status}，请先完成连接测试"}

    config = get_or_create_config(session)
    if not config.api_key:
        return {"type": "error", "message": "请先在设置页面配置 API Key"}

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
        session.commit()
        return {"type": "clarification", "message": ambiguity_message}

    schema_context = build_schema_context(candidates)

    system_prompt = f"""你是一个企业级 SQL 生成助手。你的职责是根据用户的自然语言问题，生成对应的**只读 SQL 查询语句**。

规则：
1. 只能生成 SELECT 语句，严禁生成 INSERT / UPDATE / DELETE / DROP / ALTER 等写操作。
2. 如果用户的问题不够清晰，你应该先进行澄清，而不是猜测。
3. 数据库类型为 {ds.db_type}，请使用对应方言。
4. 返回 JSON 格式，只允许以下两种：
   - 澄清：{{"type": "clarification", "message": "你的澄清问题"}}
   - SQL：{{"type": "sql_candidate", "sql": "SELECT ...", "explanation": "这条 SQL 的含义"}}
5. 不要返回任何其他格式。

以下是该数据源的表结构：
{schema_context}
"""

    try:
        with httpx.Client(timeout=config.timeout) as client:
            resp = client.post(
                f"{config.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": config.model_name,
                    "temperature": config.temperature,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": question}
                    ]
                }
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            
            # 尝试解析 JSON
            # 去掉可能的 markdown code block
            clean = content.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
                if clean.endswith("```"):
                    clean = clean[:-3]
                clean = clean.strip()

            result = validate_llm_result(json.loads(clean))

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
            session.commit()

            return result
    except httpx.HTTPStatusError as e:
        return {"type": "error", "message": f"LLM 请求失败 ({e.response.status_code}): {e.response.text[:200]}"}
    except json.JSONDecodeError:
        return {"type": "error", "message": f"LLM 返回了非 JSON 格式的内容: {content[:200]}"}
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
    sql_upper = sql.strip().upper()
    forbidden = ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE", "GRANT", "REVOKE"]
    for keyword in forbidden:
        if sql_upper.startswith(keyword) or f" {keyword} " in sql_upper:
            return {"status": "error", "message": f"安全拦截：禁止执行包含 {keyword} 的语句"}

    # 禁止多语句
    if ";" in sql.strip()[:-1]:
        return {"status": "error", "message": "安全拦截：禁止执行多条语句"}

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
            session.commit()

        # 查找字段中文备注
        column_comments = {}
        tables = session.exec(select(SchemaTable).where(SchemaTable.datasource_id == datasource_id)).all()
        for t in tables:
            fields = session.exec(select(SchemaField).where(SchemaField.table_id == t.id)).all()
            for f in fields:
                # 优先使用补充备注，其次使用原始备注
                comment = f.supplementary_comment or f.original_comment or f.name
                column_comments[f.name] = comment

        return {
            "status": "success" if rows else "empty",
            "columns": columns,
            "column_comments": column_comments,
            "rows": rows,
            "row_count": len(rows),
            "duration_ms": duration_ms
        }
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
            session.commit()

        return {"status": "error", "message": str(e)}
