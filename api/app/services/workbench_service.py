import json
import re
from pathlib import Path
from typing import Generator
from sqlmodel import Session, select
from app.models.datasource import DataSource, DataSourceStatus, SyncStatus
from app.models.schema import SchemaTable, SchemaField
from app.models.knowledge import KnowledgeSyncTask
from app.models.audit_log import AuditLog
import sqlalchemy
import time
from app.services.datasource_service import build_connect_args, build_database_url
from app.core.config import settings
from app.services.hermes_service import iter_hermes_session_json, run_hermes_session_json
from app.services import setting_service
from app.services.path_utils import sanitize_path_segment
import sqlglot
from sqlglot import exp

SQLGLOT_DIALECT_MAP = {
    "mysql": "mysql",
    "postgresql": "postgres",
    "oracle": "oracle",
}

STOP_WORDS = {
    "查询", "多少", "什么", "哪些", "怎么", "一下", "数据", "统计", "上周", "本周", "昨天", "今天", "最近",
    "id", "f_id", "0", "1", "默认", "所有", "授予", "状态", "类型", "标志", "备注", "时间", "日期", 
    "是否", "列表", "信息", "关联", "关联表", "信息表", "表结构"
}
COMMON_IDENTIFIER_PREFIXES = {"sys", "tbl", "tb", "dim", "fact", "ods", "dwd", "dws", "ads", "mdm"}


def _split_identifier_segments(value: str) -> list[str]:
    return [part for part in re.split(r"[_\W]+", value.lower()) if part]


def _looks_like_identifier(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9_]+", value.lower()))


def _is_composite_schema_alias(value: str) -> bool:
    if not _looks_like_identifier(value):
        return False
    parts = [part for part in _split_identifier_segments(value) if part not in COMMON_IDENTIFIER_PREFIXES]
    return len(parts) >= 2


def _is_relationship_like_text(value: str) -> bool:
    return "关联" in value


def _token_matches_haystack(token: str, haystack: str) -> bool:
    if not token or not haystack:
        return False

    token_lower = token.lower()
    haystack_lower = haystack.lower()
    if token_lower == haystack_lower:
        return True

    if _looks_like_identifier(haystack_lower):
        segments = _split_identifier_segments(haystack_lower)
        if _looks_like_identifier(token_lower):
            if "_" in token_lower:
                return token_lower == haystack_lower
            return token_lower in segments
        return token_lower in segments

    return token_lower in haystack_lower


def _extract_semantic_tokens(text: str) -> set[str]:
    terms: set[str] = set()
    for token in re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]{2,}", text.lower()):
        if token not in STOP_WORDS:
            terms.add(token)
        if re.fullmatch(r"[\u4e00-\u9fff]+", token):
            for size in range(2, min(5, len(token) + 1)):
                for idx in range(0, len(token) - size + 1):
                    piece = token[idx:idx + size]
                    if piece not in STOP_WORDS:
                        terms.add(piece)
    return terms


def build_dynamic_aliases(payload: list[dict]) -> dict[str, list[str]]:
    """从 Schema 的 name / original_comment / supplementary_comment 自动构建双向别名。

    同一个实体（表或字段）的物理名、原始备注、补充备注天然互为别名，
    例如字段 full_name (原始备注: 姓名, 补充备注: 员工全名) 会生成：
      full_name -> [姓名, 员工全名]
      姓名     -> [full_name, 员工全名]
      员工全名  -> [full_name, 姓名]
    """
    aliases: dict[str, list[str]] = {}

    for item in payload:
        entities: list = [item["table"]]
        entities.extend(item["fields"])

        for entity in entities:
            identifier_terms = _extract_semantic_tokens(entity.name)
            descriptive_terms: set[str] = set()
            for raw in [
                getattr(entity, "original_comment", None),
                getattr(entity, "supplementary_comment", None),
            ]:
                if raw:
                    descriptive_terms.update(_extract_semantic_tokens(raw))

            for term in descriptive_terms:
                existing = aliases.get(term, [])
                for identifier in identifier_terms:
                    if identifier != term and identifier not in existing:
                        existing.append(identifier)
                if existing:
                    aliases[term] = existing

            for identifier in identifier_terms:
                existing = aliases.get(identifier, [])
                for term in descriptive_terms:
                    if term != identifier and term not in existing:
                        existing.append(term)
                if existing:
                    aliases[identifier] = existing

    return aliases
ALLOWED_RESPONSE_TYPES = {"clarification", "sql_candidate"}

SCHEMA_RETRIEVAL_HISTORY_LIMIT = 4
CLARIFICATION_OPTION_RE = re.compile(r"^[A-Da-d](?:[)\].、．:]|\s|$)?")


def can_ask_datasource(ds: DataSource) -> bool:
    return ds.status == DataSourceStatus.CONNECTION_OK and ds.sync_status == SyncStatus.SYNC_SUCCESS


def datasource_not_ready_message(ds: DataSource) -> str:
    return (
        f"数据源状态为 {ds.status}，同步状态为 {ds.sync_status}，"
        "请先完成连接测试并成功同步知识库"
    )


def commit_with_warning(session: Session, warning_message: str) -> str | None:
    try:
        session.commit()
        return None
    except Exception:
        session.rollback()
        return warning_message

def tokenize_question(
    question: str,
    dynamic_aliases: dict[str, list[str]] | None = None,
) -> list[str]:
    tokens = _extract_semantic_tokens(question)
    expanded_tokens = set(tokens)
    alias_source = dynamic_aliases or {}
    for token in list(tokens):
        for alias in alias_source.get(token, []):
            alias_lower = alias.lower()
            if alias_lower not in STOP_WORDS:
                if not _looks_like_identifier(token) and (
                    _is_composite_schema_alias(alias_lower) or _is_relationship_like_text(alias_lower)
                ):
                    continue
                expanded_tokens.add(alias_lower)
    return sorted(expanded_tokens, key=len, reverse=True)


def is_clarification_option_answer(question: str) -> bool:
    normalized = (question or "").strip()
    if not normalized:
        return False
    return bool(CLARIFICATION_OPTION_RE.fullmatch(normalized))


def should_allow_schema_fallback(
    question: str,
    history: list[dict] | None = None,
    hermes_session_id: str | None = None,
) -> bool:
    has_history = bool(history)
    if hermes_session_id and has_history and is_clarification_option_answer(question):
        return False
    return True


def collect_table_payload(session: Session, datasource_id: int) -> list[dict]:
    tables = session.exec(select(SchemaTable).where(SchemaTable.datasource_id == datasource_id)).all()
    payload = []
    for table in tables:
        fields = session.exec(select(SchemaField).where(SchemaField.table_id == table.id)).all()
        payload.append({"table": table, "fields": fields})
    return payload


def get_datasource_knowledge_dir(vault_root: str, datasource_name: str) -> Path:
    return Path(vault_root) / sanitize_path_segment(datasource_name) / "tables"




def retrieve_relevant_schema(
    session: Session,
    datasource_id: int,
    question: str,
    limit: int = 10,
    allow_fallback: bool = True,
) -> list[dict]:
    payload = collect_table_payload(session, datasource_id)
    if not payload:
        return []
    dynamic_aliases = build_dynamic_aliases(payload)
    tokens = tokenize_question(question, dynamic_aliases)

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
                if _token_matches_haystack(token, haystack):
                    score += 2 if haystack == table.name.lower() else 1
                    matched_terms.add(token)
                    break

        if score > 0:
            ranked.append({"score": score, "matched_terms": matched_terms, **item})

    if not ranked:
        if not allow_fallback:
            return []
        return payload[: min(limit, len(payload))]

    ranked.sort(key=lambda item: (item["score"], len(item["matched_terms"])), reverse=True)
    top_score = ranked[0]["score"]
    # 采用比例阈值代替固定差值，防止某一张表由于同义词别名命中过多（score畸高）而挤掉其他相关的表
    narrowed = [
        item for item in ranked
        if item["score"] >= max(1, top_score * 0.15)
    ]
    return narrowed[:limit]


def normalize_note_name(note: str) -> str:
    name = Path(str(note)).stem
    return sanitize_path_segment(name)


def note_used_payload(note_name: str) -> dict:
    return {"note": normalize_note_name(note_name), "comment": ""}


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


def clean_obsidian_note_text(text: str) -> str:
    """清理 Obsidian 笔记中的冗余信息，避免与 Schema Context 重复。"""
    # 1. 移除顶部的 YAML Frontmatter
    text = re.sub(r"^---\n.*?\n---\n*", "", text, flags=re.DOTALL)
    
    # 2. 移除重复的表名大标题和面包屑返回链接
    text = re.sub(r"^# .*?\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[\[\.\./index\|.*?\]\]\n*", "", text)
    
    # 3. 移除完全重复的“核心字段解读”模块及其下面所有的列表项，直到遇到下一个 H2 标题
    text = re.sub(r"## 核心字段解读\n.*?(?=\n## |\Z)", "", text, flags=re.DOTALL)
    
    # 4. 移除概述类模块（因为表名和原始备注在 Schema Context 中已提供）
    #    兼容新格式“概述”及旧格式“基础信息”/“用途说明”
    for heading in ("概述", "基础信息", "用途说明"):
        text = re.sub(rf"## {heading}\n.*?(?=\n## |\Z)", "", text, flags=re.DOTALL)
    
    # 5. 移除“字段明细”及其后面的所有表格内容
    marker = "## 字段明细"
    index = text.find(marker)
    if index != -1:
        text = text[:index]
        
    # 清理多余的连续空行
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def read_relevant_table_notes(candidates: list[dict], knowledge_dir: Path, limit: int = 10) -> tuple[str, list[str]]:
    """读取候选表对应的 Obsidian 笔记；Obsidian 只作为业务补充。"""
    if not candidates:
        return "（没有匹配到候选表笔记）", []

    sections = []
    used_notes = []
    for item in candidates[:limit]:
        table = item["table"]
        note_name = sanitize_path_segment(table.name)
        note_path = knowledge_dir / f"{note_name}.md"
        if not note_path.exists():
            continue
        text = note_path.read_text(encoding="utf-8", errors="ignore").strip()
        text = clean_obsidian_note_text(text)
        if not text:
            continue
        if len(text) > 4000:
            text = truncate_text_on_line_boundary(text, 4000)
        used_notes.append(note_name)
        sections.append(f"### Note: {note_name}\n{text}")

    if not sections:
        return "（候选表没有可读取的 Obsidian 笔记）", []
    return "\n\n".join(sections), used_notes


def truncate_text_on_line_boundary(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text

    cut = text.rfind("\n", 0, limit)
    if cut <= 0:
        cut = limit
    return text[:cut].rstrip() + "\n（后续内容已裁剪）"


def schema_index_from_candidates(candidates: list[dict]) -> dict[str, set[str]]:
    index = {}
    for item in candidates:
        table = item["table"]
        index[table.name.lower()] = {field.name.lower() for field in item["fields"]}
    return index


def validate_sql_against_schema(sql: str, candidates: list[dict], db_type: str = None) -> dict:
    """基于 sqlglot AST 解析做表字段校验，防止 Hermes 使用上下文外字段。"""
    base_validation = validate_sql_candidate(sql, db_type)
    if base_validation["status"] == "invalid":
        return base_validation

    normalized_sql = base_validation["normalized_sql"]
    schema_index = schema_index_from_candidates(candidates)
    reasons = []
    warnings = []
    
    # 建立字段到表名的反向映射（用于校验未限定字段）
    all_available_fields = {}
    for t_name, fields in schema_index.items():
        for f in fields:
            if f not in all_available_fields:
                all_available_fields[f] = []
            all_available_fields[f].append(t_name)

    try:
        glot_dialect = SQLGLOT_DIALECT_MAP.get(db_type, db_type)
        parsed = sqlglot.parse_one(normalized_sql, read=glot_dialect)

        # 1. 校验表
        # 使用 set 避免重复错误消息
        seen_tables = set()
        for table in parsed.find_all(exp.Table):
            t_name = table.name.lower()
            if t_name not in schema_index and t_name not in seen_tables:
                reasons.append(f"SQL 引用了未在本轮 Schema Context 中提供的表 {table.name}")
                seen_tables.add(t_name)

        # 2. 校验字段
        for column in parsed.find_all(exp.Column):
            col_name = column.name.lower()
            table_alias = column.table.lower() if column.table else None
            
            if table_alias:
                # 尝试解析别名对应的真实表名
                real_table = None
                # 在解析树中向上查找或遍历 Table 节点寻找别名定义
                for table in parsed.find_all(exp.Table):
                    if (table.alias or table.name).lower() == table_alias:
                        real_table = table.name.lower()
                        break
                
                if real_table:
                    if real_table in schema_index:
                        if col_name not in schema_index[real_table]:
                            reasons.append(f"SQL 引用了表 {real_table} 中不存在的字段 {column.name}")
                    else:
                        # 表不在 context 中，已经在上面 Table 校验中处理了
                        pass
                else:
                    # 可能是 CTE 别名或未识别的别名
                    # sqlglot 在解析时通常能处理大多数情况，如果找不到则记录原因
                    reasons.append(f"SQL 引用了无法识别的表别名或 CTE {column.table}")
            else:
                # 未限定字段：检查是否存在于任何候选表中
                if col_name not in all_available_fields:
                    # 可能是 SELECT 别名引用或特殊函数，记为 warning
                    warnings.append(f"SQL 中的未限定标识符 {column.name} 未在候选字段中命中，可能是别名引用或方言特有语法")
    except Exception as e:
        reasons.append(f"SQL 语义分析失败: {str(e)}")

    return {
        "status": "invalid" if reasons else "valid",
        "normalized_sql": normalized_sql,
        "reasons": reasons,
        "warnings": warnings,
    }





def validate_llm_result(result: dict) -> dict:
    result_type = result.get("type")
    if result_type not in ALLOWED_RESPONSE_TYPES:
        raise ValueError("LLM 返回了不支持的结果类型")
    if result_type == "clarification" and not result.get("message"):
        raise ValueError("LLM 返回澄清结果但缺少 message")
    if result_type == "sql_candidate" and not result.get("sql"):
        raise ValueError("LLM 返回 SQL 候选但缺少 sql")
    used_notes = result.get("used_notes")
    if used_notes is not None and not isinstance(used_notes, list):
        raise ValueError("LLM 返回的 used_notes 必须是数组")
    return result


FOOD_DELIVERY_TERMS = ["餐饮", "外卖", "美食", "快餐", "餐厅", "食品"]
CLASSIFICATION_FIELD_TERMS = [
    "category",
    "type",
    "biz_type",
    "product_type",
    "order_type",
    "merchant_category",
    "merchant_type",
    "分类",
    "品类",
    "类目",
    "餐饮分类",
    "商品分类",
]


def guard_sql_candidate_against_missing_semantics(result: dict, knowledge_dir: Path) -> dict:
    if result.get("type") != "sql_candidate":
        return result

    sql = result.get("sql") or ""
    if not _uses_food_delivery_name_guess(sql):
        return result

    notes_text = _read_used_notes_text(result.get("used_notes") or [], knowledge_dir)
    if _has_classification_semantics(notes_text):
        return result

    return {
        "type": "clarification",
        "message": "\n".join([
            "user_orders 表没有明确的餐饮/外卖分类字段。是否允许用 product_name 关键词进行模糊匹配？",
            "A) 允许，用 product_name 关键词匹配餐饮/外卖",
            "B) 不允许，请只查询今天全部订单",
            "C) 我补充餐饮/外卖的判断规则",
            "D) 取消本次 SQL 生成",
        ]),
        "used_notes": result.get("used_notes") or [],
    }


def _uses_food_delivery_name_guess(sql: str) -> bool:
    normalized = sql.lower()
    return "product_name" in normalized and " like " in normalized and any(term in sql for term in FOOD_DELIVERY_TERMS)


def _read_used_notes_text(used_notes: list, knowledge_dir: Path) -> str:
    parts = []
    for note in used_notes:
        note_name = normalize_note_name(str(note))
        note_path = knowledge_dir / f"{note_name}.md"
        if note_path.exists():
            parts.append(note_path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def _has_classification_semantics(text: str) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in CLASSIFICATION_FIELD_TERMS)


def normalize_sql(sql: str) -> str:
    no_block_comments = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    no_line_comments = re.sub(r"--.*?$", " ", no_block_comments, flags=re.M)
    collapsed = re.sub(r"\s+", " ", no_line_comments).strip()
    # 移除末尾的分号，方便后续判断是否为多条语句
    return collapsed.rstrip(";")


def validate_sql_candidate(sql: str, db_type: str = None) -> dict:
    normalized_sql = normalize_sql(sql)
    if not normalized_sql:
        return {"status": "invalid", "normalized_sql": normalized_sql, "reasons": ["SQL 为空"]}

    reasons = []
    try:
        glot_dialect = SQLGLOT_DIALECT_MAP.get(db_type, db_type)
        # 尝试解析
        expressions = sqlglot.parse(normalized_sql, read=glot_dialect)
        if not expressions:
            reasons.append("无法解析的 SQL 语句")
        elif len(expressions) > 1:
            reasons.append("禁止执行多条语句（检测到分号分隔的多条查询）")
        else:
            expression = expressions[0]
            # 1. 检查只读操作
            if not isinstance(expression, (exp.Select, exp.Union, exp.With)):
                reasons.append("仅允许 SELECT 或 WITH 开头的只读查询")
            
            # 2. 深度遍历检查危险操作（防止在子查询中嵌套写操作）
            forbidden_types = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Alter, exp.Create)
            for node in expression.walk():
                if isinstance(node, forbidden_types):
                    reasons.append(f"禁止执行包含 {node.key.upper()} 的写操作")
                    break
    except Exception as e:
        reasons.append(f"SQL 语法错误: {str(e)}")

    return {
        "status": "invalid" if reasons else "valid",
        "normalized_sql": normalized_sql,
        "reasons": reasons,
    }

# ---------------------------------------------------------------------------
# 公共 prompt / 日志辅助函数（ask_llm 和 ask_llm_stream 共用）
# ---------------------------------------------------------------------------

def _build_system_prompt(db_type: str) -> str:
    """构建系统 prompt"""
    return f"""你是一个企业级 SQL 生成助手。你当前的任务是在系统提供的受控上下文中判断意图、识别歧义、提出关系补全建议，并生成只读 SQL 或提出澄清。

规则：
1. 【禁止写操作】只能生成 SELECT 语句，严禁生成 INSERT / UPDATE / DELETE / DROP / ALTER 等任何修改数据的操作。
2. 【严禁猜测】当用户输入模糊、有歧义、或缺少关键信息（如无法确定具体表名、缺少必要过滤字段等）时，必须进入澄清模式，严禁盲目生成 SQL。
3. 【强制选项】在澄清模式下，你必须列出最多 4 个具体的候选项（标记为 A、B...）让用户点击或回复选择，而不是空泛地提问。
4. 数据库类型为 {db_type}，请使用对应方言。
5. Schema Context 来自系统 SQLite 元数据，是唯一可信的表字段来源。禁止使用未出现在 Schema Context 中的表、字段和关系。
6. Obsidian Notes 仅作为业务解释和口径参考，不可覆盖 Schema Context。
7. 你可以基于候选表字段和 Obsidian Notes 判断歧义、提出澄清、建议 join，但不得编造不存在的字段、枚举或关联。
8. 如果用户选择了澄清选项，但该选项依赖表中不存在的字段、枚举或分类口径，必须再次进入澄清模式。禁止使用 LIKE 关键词、名称猜测、枚举猜测来替代缺失字段，除非用户明确允许模糊匹配。
9. 返回 JSON 格式，只允许以下两种：
   - 澄清：{{"type": "clarification", "message": "问题存在歧义，请选择最符合您需求的选项：\nA) ...\nB) ...", "used_notes": ["已读取的笔记文件名"]}}
   - SQL：{{"type": "sql_candidate", "sql": "SELECT ...", "explanation": "SQL 含义说明", "used_notes": ["已读取的笔记文件名"]}}
10. 不要返回任何 JSON 以外的文字。
"""


def _build_full_prompt(
    system_prompt: str,
    question: str,
    schema_context: str,
    obsidian_context: str,
) -> str:
    """构建当前轮 prompt。多轮上下文交给 Hermes session 持有。"""
    prompt_lines = [system_prompt, ""]

    prompt_lines.extend([
        f"### 用户当前问题：{question}",
        "",
        "### Schema Context",
        schema_context,
        "",
        "### Obsidian Notes",
        obsidian_context,
        "",
        "执行要求：",
        "1. 如果用户的问题是对之前澄清的回应，请结合上下文生成 SQL。",
        "2. 判断歧义和补全关系时只能在 Schema Context 提供的候选范围内进行。",
        "3. Obsidian Notes 只用于业务语义、口径、注意事项补充。",
        "4. 严格返回 JSON 格式。",
    ])
    return "\n".join(prompt_lines)


def should_use_incremental_prompt(
    question: str,
    history: list[dict] | None,
    candidates: list[dict],
    hermes_session_id: str | None
) -> bool:
    """判断当前轮次是否应该使用轻量级的增量 prompt"""
    if not hermes_session_id or not history:
        return False
        
    last_assistant_msg = next((msg for msg in reversed(history) if msg.get("role") == "assistant"), None)
    if not last_assistant_msg:
        return False
        
    # 如果上一轮是澄清（包含选项或提示），且用户的回答比较简短（像是选择选项或简单回答）
    last_content = str(last_assistant_msg.get("content", ""))
    if ("选择" in last_content or "澄清" in last_content or "歧义" in last_content) and len(question.strip()) <= 20:
        return True
        
    return False


def build_clarification_session_summary(history: list[dict] | None) -> str:
    """从历史记录中提取上一轮的澄清摘要"""
    if not history:
        return "无"
        
    last_clarification = ""
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            last_clarification = str(msg.get("content", ""))
            break
            
    if not last_clarification:
        return "无"
        
    lines = ["- 上一轮澄清问题："]
    for line in last_clarification.split("\n"):
        if line.strip():
            lines.append(f"  {line.strip()}")
    return "\n".join(lines)


def build_minimal_schema_context(candidates: list[dict]) -> str:
    """构建极致压缩的 schema context，仅包含表名和字段名"""
    tables = candidates or []
    if not tables:
        return "（该数据源暂无同步的表结构）"

    lines = []
    # 限制最多 10 张表，每张表最多 12 个字段
    for item in tables[:10]:
        t = item["table"]
        lines.append(f"\n### 表: {t.name}")
        for f in item["fields"][:12]:
            lines.append(f"  - {f.name} ({f.type})")
    return "\n".join(lines)


def _build_incremental_prompt(
    system_prompt: str,
    question: str,
    minimal_schema: str,
    session_summary: str,
) -> str:
    """构建多轮澄清场景下的增量 prompt"""
    prompt_lines = [
        system_prompt,
        "",
        "你正在继续同一轮 SQL 澄清会话。",
        "必须遵守：",
        "1. 只返回 JSON",
        "2. 只使用当前候选 Schema 中存在的表和字段",
        "3. 如果信息仍不足，继续澄清，不要猜测",
        "",
        "### 会话摘要",
        session_summary,
        "",
        "### 最小 Schema Context",
        minimal_schema,
    ]
    prompt_lines.extend([
        "",
        f"### 本轮用户回复：{question}"
    ])
    
    return "\n".join(prompt_lines)


def prepare_question_context(
    session: Session,
    datasource_id: int,
    question: str,
    knowledge_dir: Path,
    vault_root: str = "",
    datasource_name: str = "",
    history: list[dict] | None = None,
    hermes_session_id: str | None = None,
) -> tuple[list[dict], str, str, list[str]]:
    retrieval_question = build_schema_retrieval_question(question, history)
    candidates = retrieve_relevant_schema(
        session,
        datasource_id,
        retrieval_question,
        allow_fallback=should_allow_schema_fallback(question, history, hermes_session_id),
    )
    schema_context = build_schema_context(candidates)
    obsidian_context, note_names = read_relevant_table_notes(candidates, knowledge_dir)

    return candidates, schema_context, obsidian_context, note_names


def build_schema_retrieval_question(question: str, history: list[dict] | None = None) -> str:
    history_parts = []
    for item in history or []:
        if item.get("role") == "user" and item.get("content"):
            history_parts.append(str(item["content"]))

    if is_clarification_option_answer(question):
        last_assistant_content = next(
            (
                str(item.get("content"))
                for item in reversed(history or [])
                if item.get("role") == "assistant" and item.get("content")
            ),
            "",
        )
        if last_assistant_content:
            history_parts.append(last_assistant_content)

    parts = history_parts[-SCHEMA_RETRIEVAL_HISTORY_LIMIT:]
    parts.append(question)
    return "\n".join(parts)


def validate_and_guard_result(result: dict, knowledge_dir: Path, candidates: list[dict], db_type: str = None) -> dict:
    guarded = guard_sql_candidate_against_missing_semantics(result, knowledge_dir)
    if guarded.get("type") != "sql_candidate":
        return guarded

    validation = validate_sql_against_schema(guarded.get("sql") or "", candidates, db_type)
    if validation["status"] == "invalid":
        return {
            "type": "error",
            "message": "；".join(validation["reasons"]),
            "used_notes": guarded.get("used_notes") or [],
        }
    if validation.get("warnings"):
        existing_warning = guarded.get("warning")
        schema_warning = "；".join(validation["warnings"])
        guarded["warning"] = f"{existing_warning}；{schema_warning}" if existing_warning else schema_warning
    return guarded


def clarification_has_schema_contradiction(result: dict, candidates: list[dict]) -> bool:
    if result.get("type") != "clarification":
        return False

    message = str(result.get("message") or "")
    if not message or "schema" not in message.lower():
        return False

    contradiction_hints = ("补充", "缺少", "无法从当前可用表中获取")
    if not any(hint in message for hint in contradiction_hints):
        return False

    candidate_tables = {item["table"].name for item in candidates if item.get("table")}
    return any(table_name in message for table_name in candidate_tables)


def build_clarification_retry_prompt(
    system_prompt: str,
    question: str,
    schema_context: str,
    obsidian_context: str,
    candidates: list[dict],
) -> str:
    candidate_tables = "、".join(item["table"].name for item in candidates if item.get("table")) or "（无候选表）"
    base_prompt = _build_full_prompt(system_prompt, question, schema_context, obsidian_context)
    retry_lines = [
        "",
        "补充纠错要求：",
        f"1. 当前 Schema Context 已经包含这些候选表：{candidate_tables}。",
        "2. 禁止声称这些候选表缺少 schema 或不可用。",
        "3. 如果当前表已经足够回答问题，请直接生成 SQL；如果仍需澄清，只能基于这些已提供的表和字段给出选项。",
        "4. 严格返回 JSON，不要输出额外说明。",
    ]
    return "\n".join([base_prompt, *retry_lines])


def _log_result(session: Session, datasource_id: int, ds_name: str,
               question: str, result: dict) -> tuple[str | None, int | None]:
    """记录结果审计日志，返回 (warning, log_id)"""
    log = AuditLog(
        datasource_id=datasource_id,
        datasource_name=ds_name,
        question=question,
        clarified=result.get("type") == "clarification",
        clarification_content=result.get("message") if result.get("type") == "clarification" else None,
        sql=result.get("sql"),
        used_notes=json.dumps(result.get("used_notes", []), ensure_ascii=False) if result.get("used_notes") is not None else None,
        executed=False,
    )
    session.add(log)
    warning = commit_with_warning(session, "问答成功，但审计日志写入失败")
    if not warning:
        session.refresh(log)
        return None, log.id
    return warning, None


def build_display_result(
    raw_hermes_result: dict | None,
    processed_result: dict,
    audit_log_id: int | None = None,
    hermes_session_id: str | None = None,
    warning: str | None = None,
) -> dict:
    display_result = dict(raw_hermes_result or processed_result)
    if audit_log_id:
        display_result["audit_log_id"] = audit_log_id
    if hermes_session_id:
        display_result["hermes_session_id"] = hermes_session_id
    if warning:
        display_result["warning"] = warning
    if processed_result.get("type") == "error":
        display_result["system_error"] = processed_result.get("message", "系统校验未通过")
        display_result["processed_result_type"] = "error"
    return display_result


# ---------------------------------------------------------------------------
# SSE 辅助
# ---------------------------------------------------------------------------

def _sse_event(event: str, data: dict) -> str:
    """格式化一个 SSE 事件"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# ask_llm — 原有同步端点（保留向后兼容）
# ---------------------------------------------------------------------------

def ask_llm(
    session: Session,
    datasource_id: int,
    question: str,
    history: list[dict] | None = None,
    hermes_session_id: str | None = None,
) -> dict:
    """核心问答：SQLite 先召回事实上下文，再让 Hermes 判断歧义或生成 SQL。"""
    ds = session.get(DataSource, datasource_id)
    if not ds:
        return {"type": "error", "message": "数据源不存在"}

    if not can_ask_datasource(ds):
        return {"type": "error", "message": datasource_not_ready_message(ds)}

    vault_root = setting_service.get_setting(session, "obsidian_vault_root", settings.OBSIDIAN_VAULT_ROOT)
    hermes_cli_path = setting_service.get_setting(session, "hermes_cli_path", settings.HERMES_CLI_PATH)

    knowledge_dir = get_datasource_knowledge_dir(vault_root, ds.name)
    if not knowledge_dir.exists():
        return {"type": "error", "message": "当前数据源还没有可用知识库，请先完成同步到知识库后再问答"}

    try:
        candidates, schema_context, obsidian_context, _note_names = prepare_question_context(
            session,
            datasource_id,
            question,
            knowledge_dir,
            vault_root=vault_root,
            datasource_name=ds.name,
            history=history,
            hermes_session_id=hermes_session_id,
        )
        system_prompt = _build_system_prompt(ds.db_type)
        prompt = _build_full_prompt(system_prompt, question, schema_context, obsidian_context)
        hermes_response = run_hermes_session_json(
            prompt,
            cwd=str(knowledge_dir),
            hermes_cli_path=hermes_cli_path,
            session_id=hermes_session_id,
        )
        if len(hermes_response) == 3:
            raw_result, raw_hermes_result, next_hermes_session_id = hermes_response
        else:
            raw_result, next_hermes_session_id = hermes_response
            raw_hermes_result = raw_result
        result = validate_llm_result(raw_result)
        result = validate_and_guard_result(result, knowledge_dir, candidates, ds.db_type)
        if clarification_has_schema_contradiction(result, candidates):
            retry_prompt = build_clarification_retry_prompt(
                system_prompt,
                question,
                schema_context,
                obsidian_context,
                candidates,
            )
            retry_response = run_hermes_session_json(
                retry_prompt,
                cwd=str(knowledge_dir),
                hermes_cli_path=hermes_cli_path,
                session_id=next_hermes_session_id or hermes_session_id,
            )
            if len(retry_response) == 3:
                retry_raw_result, retry_raw_hermes_result, retry_session_id = retry_response
            else:
                retry_raw_result, retry_session_id = retry_response
                retry_raw_hermes_result = retry_raw_result
            result = validate_llm_result(retry_raw_result)
            result = validate_and_guard_result(result, knowledge_dir, candidates, ds.db_type)
            raw_hermes_result = retry_raw_hermes_result or raw_hermes_result
            next_hermes_session_id = retry_session_id or next_hermes_session_id

        warning, log_id = _log_result(session, datasource_id, ds.name, question, result)
        display_result = build_display_result(
            raw_hermes_result,
            result,
            audit_log_id=log_id,
            hermes_session_id=next_hermes_session_id,
            warning=warning,
        )
        if result.get("type") == "error" and raw_hermes_result is None:
            return result
        return display_result
    except ValueError as e:
        return {"type": "error", "message": str(e)}
    except Exception as e:
        return {"type": "error", "message": str(e)}


# ---------------------------------------------------------------------------
# ask_llm_stream — SSE 流式端点
# ---------------------------------------------------------------------------

def ask_llm_stream(
    session: Session, 
    datasource_id: int, 
    question: str, 
    history: list[dict] | None = None,
    hermes_session_id: str | None = None,
) -> Generator[str, None, None]:
    """流式问答：通过 SSE 推送 SQLite-first 检索、Hermes 调用和校验过程。"""

    # 1. 校验数据源
    ds = session.get(DataSource, datasource_id)
    if not ds:
        yield _sse_event("error", {"message": "数据源不存在"})
        return
    if not can_ask_datasource(ds):
        yield _sse_event("error", {"message": datasource_not_ready_message(ds)})
        return

    vault_root = setting_service.get_setting(session, "obsidian_vault_root", settings.OBSIDIAN_VAULT_ROOT)
    hermes_cli_path = setting_service.get_setting(session, "hermes_cli_path", settings.HERMES_CLI_PATH)

    knowledge_dir = get_datasource_knowledge_dir(vault_root, ds.name)
    if not knowledge_dir.exists():
        yield _sse_event("error", {"message": "当前数据源还没有可用知识库，请先完成同步到知识库后再问答"})
        return
        
    latest_task = session.exec(select(KnowledgeSyncTask).where(KnowledgeSyncTask.datasource_id == datasource_id).order_by(KnowledgeSyncTask.id.desc())).first()
    if latest_task and ds.last_synced_at and latest_task.finished_at and ds.last_synced_at > latest_task.finished_at:
        yield _sse_event("status", {"phase": "warning", "message": "警告：数据源表结构已有更新，当前知识库可能已过期，建议重新同步"})

    emitted_notes = set()

    yield _sse_event("status", {"phase": "retrieving_schema", "message": "正在从 SQLite 检索候选 Schema..."})
    try:
        candidates, schema_context, obsidian_context, _note_names = prepare_question_context(
            session,
            datasource_id,
            question,
            knowledge_dir,
            vault_root=vault_root,
            datasource_name=ds.name,
            history=history,
            hermes_session_id=hermes_session_id,
        )
    except Exception as e:
        yield _sse_event("status", {"phase": "failed", "message": str(e)})
        yield _sse_event("error", {"message": str(e)})
        return

    # 2. 调用 Hermes。Hermes 在后端提供的候选 Schema 和相关笔记内判断歧义与生成 SQL。
    yield _sse_event("status", {"phase": "calling_hermes", "message": "正在调用 Hermes Agent..."})

    system_prompt = _build_system_prompt(ds.db_type)
    prompt = _build_full_prompt(system_prompt, question, schema_context, obsidian_context)

    try:
        result = None
        raw_hermes_result = None
        next_hermes_session_id = None
        for event in iter_hermes_session_json(
            prompt,
            cwd=str(knowledge_dir),
            hermes_cli_path=hermes_cli_path,
            session_id=hermes_session_id,
        ):
            if event.get("type") == "trace":
                yield _sse_event("hermes_trace", {"message": event.get("message", "")})
            elif event.get("type") == "result":
                raw_hermes_result = event.get("raw_result") or raw_hermes_result
                result = validate_llm_result(event.get("result") or {})
                result = validate_and_guard_result(result, knowledge_dir, candidates, ds.db_type)
                next_hermes_session_id = event.get("session_id")
        if result is None:
            raise RuntimeError("Hermes 返回为空")
        if clarification_has_schema_contradiction(result, candidates):
            retry_prompt = build_clarification_retry_prompt(
                system_prompt,
                question,
                schema_context,
                obsidian_context,
                candidates,
            )
            retry_response = run_hermes_session_json(
                retry_prompt,
                cwd=str(knowledge_dir),
                hermes_cli_path=hermes_cli_path,
                session_id=next_hermes_session_id or hermes_session_id,
            )
            if len(retry_response) == 3:
                retry_raw_result, retry_raw_hermes_result, retry_session_id = retry_response
            else:
                retry_raw_result, retry_session_id = retry_response
                retry_raw_hermes_result = retry_raw_result
            result = validate_llm_result(retry_raw_result)
            result = validate_and_guard_result(result, knowledge_dir, candidates, ds.db_type)
            raw_hermes_result = retry_raw_hermes_result or raw_hermes_result
            next_hermes_session_id = retry_session_id or next_hermes_session_id
    except (ValueError, RuntimeError) as e:
        yield _sse_event("status", {"phase": "failed", "message": str(e)})
        yield _sse_event("error", {"message": str(e)})
        return
    except Exception as e:
        yield _sse_event("status", {"phase": "failed", "message": str(e)})
        yield _sse_event("error", {"message": str(e)})
        return

    # 3. 推送 Hermes 最终使用的 Obsidian 笔记
    display_result = build_display_result(raw_hermes_result, result)

    for note in display_result.get("used_notes", []) or []:
        note_name = normalize_note_name(note)
        if note_name in emitted_notes:
            continue
        emitted_notes.add(note_name)
        yield _sse_event("note_used", note_used_payload(note_name))

    # 4. 记录审计日志并注入 audit_log_id
    warning, log_id = _log_result(session, datasource_id, ds.name, question, result)
    display_result = build_display_result(
        raw_hermes_result,
        result,
        audit_log_id=log_id,
        hermes_session_id=next_hermes_session_id,
        warning=warning,
    )

    if result.get("type") == "error" and raw_hermes_result is None:
        yield _sse_event("status", {"phase": "failed", "message": result.get("message", "SQL 校验失败")})
        yield _sse_event("error", result)
        return
    if result.get("type") == "error":
        yield _sse_event("status", {"phase": "failed", "message": result.get("message", "SQL 校验失败")})

    # 5. 推送结果
    if result.get("type") != "error":
        yield _sse_event("status", {"phase": "completed", "message": "已完成"})
    yield _sse_event("result", display_result)


def apply_query_limits(conn, db_type: str, timeout_ms: int = 30000):
    if db_type == "mysql":
        conn.execute(sqlalchemy.text(f"SET SESSION MAX_EXECUTION_TIME={timeout_ms}"))
    elif db_type == "postgresql":
        conn.execute(sqlalchemy.text(f"SET statement_timeout = {timeout_ms}"))
    elif db_type == "oracle":
        # oracledb 驱动通过 call_timeout 控制单次网络往返超时（毫秒）
        raw_connection = getattr(getattr(conn, "connection", None), "driver_connection", None)
        if raw_connection is not None and hasattr(raw_connection, "call_timeout"):
            raw_connection.call_timeout = timeout_ms

def execute_readonly_sql(session: Session, datasource_id: int, sql: str, audit_log_id: int | None = None) -> dict:
    """校验并执行只读 SQL，如果提供 audit_log_id 则精确更新对应日志"""
    ds = session.get(DataSource, datasource_id)
    if not ds:
        return {"status": "error", "message": "数据源不存在"}

    # 只读校验
    normalized_sql = normalize_sql(sql)
    validation = validate_sql_candidate(sql, ds.db_type)
    if validation["status"] == "invalid":
        return {"status": "error", "message": "；".join(validation["reasons"])}

    try:
        url = build_database_url(ds)
        engine = sqlalchemy.create_engine(url, connect_args=build_connect_args(ds, 10))

        start_time = time.time()
        with engine.connect() as conn:
            apply_query_limits(conn, ds.db_type, 30000)
            result = conn.execute(sqlalchemy.text(sql))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchmany(500)]
            duration_ms = int((time.time() - start_time) * 1000)

        # 更新审计日志
        log = None
        if audit_log_id:
            log = session.get(AuditLog, audit_log_id)
            
        if not log:
            # 兼容：如果前端没有回传 ID，按原逻辑回退查找
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
        log = None
        if audit_log_id:
            log = session.get(AuditLog, audit_log_id)
            
        if not log:
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
