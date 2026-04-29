import json
import httpx
from sqlmodel import Session, select
from app.models.model_config import ModelConfig
from app.models.datasource import DataSource, DataSourceStatus
from app.models.schema import SchemaTable, SchemaField
from app.models.audit_log import AuditLog
import sqlalchemy
import time

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

def build_schema_context(session: Session, datasource_id: int) -> str:
    """构建 Schema 上下文，供 LLM prompt 使用"""
    tables = session.exec(select(SchemaTable).where(SchemaTable.datasource_id == datasource_id)).all()
    if not tables:
        return "（该数据源暂无同步的表结构）"
    
    lines = []
    for t in tables:
        comment_parts = []
        if t.original_comment:
            comment_parts.append(t.original_comment)
        if t.supplementary_comment:
            comment_parts.append(f"[补充: {t.supplementary_comment}]")
        comment = " ".join(comment_parts) if comment_parts else ""
        lines.append(f"\n### 表: {t.name}  {comment}")
        
        fields = session.exec(select(SchemaField).where(SchemaField.table_id == t.id)).all()
        for f in fields:
            f_comment_parts = []
            if f.original_comment:
                f_comment_parts.append(f.original_comment)
            if f.supplementary_comment:
                f_comment_parts.append(f"[补充: {f.supplementary_comment}]")
            f_comment = " ".join(f_comment_parts) if f_comment_parts else ""
            lines.append(f"  - {f.name} ({f.type}) {f_comment}")
    
    return "\n".join(lines)

def ask_llm(session: Session, datasource_id: int, question: str) -> dict:
    """核心问答：召回 Schema -> 构建 prompt -> 调 LLM -> 返回结果"""
    ds = session.get(DataSource, datasource_id)
    if not ds:
        return {"type": "error", "message": "数据源不存在"}
    
    if ds.status not in (DataSourceStatus.READY, DataSourceStatus.CONNECTION_OK):
        return {"type": "error", "message": f"数据源状态为 {ds.status}，需要先同步成功后才能问答"}
    
    config = get_or_create_config(session)
    if not config.api_key:
        return {"type": "error", "message": "请先在设置页面配置 API Key"}
    
    schema_context = build_schema_context(session, datasource_id)
    
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
            
            result = json.loads(clean)
            
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
    except Exception as e:
        return {"type": "error", "message": str(e)}

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
        if ds.db_type == "postgresql":
            url = f"postgresql://{ds.username}:{ds.password}@{ds.host}:{ds.port}/{ds.database}"
        elif ds.db_type == "mysql":
            url = f"mysql+pymysql://{ds.username}:{ds.password}@{ds.host}:{ds.port}/{ds.database}"
        else:
            return {"status": "error", "message": f"不支持的数据库类型: {ds.db_type}"}
        
        engine = sqlalchemy.create_engine(url)
        
        start_time = time.time()
        with engine.connect() as conn:
            # 15秒超时
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
