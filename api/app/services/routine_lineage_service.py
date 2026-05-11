from __future__ import annotations

from datetime import datetime
import re

from sqlmodel import Session, delete

from app.models.routine import RoutineDefinition, RoutineSqlFact

SQL_START_PATTERN = re.compile(
    r"^\s*(with|select|insert\s+into|update|delete\s+from|merge\s+into|truncate\s+table)\b",
    re.IGNORECASE,
)
TABLE_TOKEN_PATTERN = r"[A-Za-z_][A-Za-z0-9_$#]*(?:\.[A-Za-z_][A-Za-z0-9_$#]*)?"
READ_PATTERN = re.compile(rf"\b(?:from|join|using)\s+({TABLE_TOKEN_PATTERN})\b", re.IGNORECASE)
INSERT_PATTERN = re.compile(rf"\binsert\s+into\s+({TABLE_TOKEN_PATTERN})\b", re.IGNORECASE)
UPDATE_PATTERN = re.compile(rf"\bupdate\s+({TABLE_TOKEN_PATTERN})\b", re.IGNORECASE)
DELETE_PATTERN = re.compile(rf"\bdelete\s+from\s+({TABLE_TOKEN_PATTERN})\b", re.IGNORECASE)
MERGE_PATTERN = re.compile(rf"\bmerge\s+into\s+({TABLE_TOKEN_PATTERN})\b", re.IGNORECASE)
TRUNCATE_PATTERN = re.compile(rf"\btruncate\s+table\s+({TABLE_TOKEN_PATTERN})\b", re.IGNORECASE)
EXECUTE_IMMEDIATE_PATTERN = re.compile(
    r"execute\s+immediate\s+'((?:''|[^'])+)'",
    re.IGNORECASE | re.DOTALL,
)


def normalize_table_name(table_name: str) -> str:
    cleaned = (table_name or "").strip().strip('"')
    if not cleaned:
        return ""
    if cleaned.startswith("<default>."):
        cleaned = cleaned.split(".", 1)[1]
    if "." in cleaned:
        cleaned = cleaned.split(".")[-1]
    return cleaned.strip('"').lower()


def extract_sql_statements(definition_text: str) -> list[tuple[str, bool]]:
    statements: list[tuple[str, bool]] = []
    current_lines: list[str] = []

    for raw_line in (definition_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if current_lines:
            current_lines.append(line)
            if _has_statement_terminator(line):
                statements.append(("\n".join(current_lines).strip().rstrip(";"), False))
                current_lines = []
            continue

        if SQL_START_PATTERN.match(line):
            current_lines = [line]
            if _has_statement_terminator(line):
                statements.append(("\n".join(current_lines).strip().rstrip(";"), False))
                current_lines = []

        for match in EXECUTE_IMMEDIATE_PATTERN.finditer(raw_line):
            dynamic_sql = match.group(1).replace("''", "'").strip().rstrip(";")
            if dynamic_sql and SQL_START_PATTERN.match(dynamic_sql):
                statements.append((dynamic_sql, True))

    if current_lines:
        statements.append(("\n".join(current_lines).strip().rstrip(";"), False))

    return statements


def _extract_table_names(pattern: re.Pattern[str], sql: str) -> set[str]:
    return {match.group(1) for match in pattern.finditer(sql)}


def _has_statement_terminator(line: str) -> bool:
    in_single_quote = False
    idx = 0
    while idx < len(line):
        char = line[idx]
        if char == "'":
            if in_single_quote and idx + 1 < len(line) and line[idx + 1] == "'":
                idx += 2
                continue
            in_single_quote = not in_single_quote
        elif char == ";" and not in_single_quote:
            return True
        idx += 1
    return False


def _strip_block_comments(sql: str) -> str:
    without_complete_blocks = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    without_open_tail = re.sub(r"/\*.*$", " ", without_complete_blocks, flags=re.DOTALL)
    without_close_tail = without_open_tail.replace("*/", " ")
    return without_close_tail


def _strip_line_comments(sql: str) -> str:
    lines: list[str] = []
    for raw_line in sql.splitlines():
        line = raw_line
        if "--" in line:
            comment_idx = line.index("--")
            in_single_quote = False
            idx = 0
            while idx < comment_idx:
                char = line[idx]
                if char == "'":
                    if in_single_quote and idx + 1 < comment_idx and line[idx + 1] == "'":
                        idx += 2
                        continue
                    in_single_quote = not in_single_quote
                idx += 1
            if not in_single_quote:
                line = line[:comment_idx]
        lines.append(line)
    return "\n".join(lines)


def _normalize_whitespace(sql: str) -> str:
    return "\n".join(line.rstrip() for line in sql.splitlines() if line.strip()).strip()


def _remove_insert_target_alias(sql: str) -> str:
    return re.sub(
        rf"(?is)\b(insert\s+into\s+{TABLE_TOKEN_PATTERN})\s+[A-Za-z_][A-Za-z0-9_$#]*\s*(\()",
        r"\1 \2",
        sql,
    )


def _clean_statement_for_sqllineage(statement_text: str) -> str:
    cleaned = _strip_block_comments(statement_text)
    cleaned = _strip_line_comments(cleaned)
    cleaned = _remove_insert_target_alias(cleaned)
    cleaned = _normalize_whitespace(cleaned)
    return cleaned


def _fallback_parse_statement(statement_text: str) -> tuple[set[str], set[str]]:
    reads = _extract_table_names(READ_PATTERN, statement_text)
    writes = set()
    writes.update(_extract_table_names(INSERT_PATTERN, statement_text))
    writes.update(_extract_table_names(UPDATE_PATTERN, statement_text))
    writes.update(_extract_table_names(DELETE_PATTERN, statement_text))
    writes.update(_extract_table_names(MERGE_PATTERN, statement_text))
    writes.update(_extract_table_names(TRUNCATE_PATTERN, statement_text))
    return reads, writes


def parse_statement_tables(statement_text: str) -> tuple[set[str], set[str], str]:
    cleaned_statement = _clean_statement_for_sqllineage(statement_text)
    try:
        from sqllineage.runner import LineageRunner

        runner = LineageRunner(cleaned_statement, dialect="oracle")
        reads = {normalize_table_name(str(table)) for table in getattr(runner, "source_tables", set())}
        writes = {normalize_table_name(str(table)) for table in getattr(runner, "target_tables", set())}
        reads.discard("")
        writes.discard("")
        if not reads and not writes:
            reads, writes = _fallback_parse_statement(statement_text)
            return reads, writes, "regex-fallback"
        return reads, writes, "sqllineage"
    except Exception:
        reads, writes = _fallback_parse_statement(statement_text)
        return reads, writes, "regex-fallback"


def rebuild_routine_sql_facts(
    session: Session,
    *,
    datasource_id: int,
    routines: list[RoutineDefinition],
) -> None:
    session.exec(delete(RoutineSqlFact).where(RoutineSqlFact.datasource_id == datasource_id))

    now = datetime.now()
    for routine in routines:
        statements = extract_sql_statements(routine.definition_text or "")
        fact_count = 0
        parser_names: set[str] = set()

        for statement_index, (statement_text, is_dynamic) in enumerate(statements):
            read_tables, write_tables, parser_name = parse_statement_tables(statement_text)
            parser_names.add(parser_name)

            for table_name in sorted(read_tables):
                normalized = normalize_table_name(table_name)
                if not normalized:
                    continue
                session.add(
                    RoutineSqlFact(
                        datasource_id=datasource_id,
                        routine_id=routine.id,
                        statement_index=statement_index,
                        statement_text=statement_text,
                        table_name=normalize_table_name(table_name),
                        normalized_table_name=normalized,
                        usage_type="read",
                        parser_name=parser_name,
                        is_dynamic=is_dynamic,
                        created_at=now,
                        updated_at=now,
                    )
                )
                fact_count += 1

            for table_name in sorted(write_tables):
                normalized = normalize_table_name(table_name)
                if not normalized:
                    continue
                session.add(
                    RoutineSqlFact(
                        datasource_id=datasource_id,
                        routine_id=routine.id,
                        statement_index=statement_index,
                        statement_text=statement_text,
                        table_name=normalize_table_name(table_name),
                        normalized_table_name=normalized,
                        usage_type="write",
                        parser_name=parser_name,
                        is_dynamic=is_dynamic,
                        created_at=now,
                        updated_at=now,
                    )
                )
                fact_count += 1

        routine.lineage_updated_at = now
        if fact_count > 0:
            routine.lineage_status = "parsed"
            routine.lineage_message = f"解析出 {fact_count} 条表使用事实（{', '.join(sorted(parser_names))}）"
        elif statements:
            routine.lineage_status = "no_table_fact"
            routine.lineage_message = "已抽取 SQL，但未识别出明确表关系"
        else:
            routine.lineage_status = "no_sql"
            routine.lineage_message = "未从过程原文中抽取到可解析 SQL"
        session.add(routine)
