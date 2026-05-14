from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re

from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select

from app.models.datasource import DataSource, SourceMode, SourceStatus
from app.models.routine import RoutineDefinition
from app.models.schema import SchemaField, SchemaTable
from app.models.sql_import import SqlImportBatch, SqlImportBatchStatus, SqlImportFile
from app.models.view import ViewDefinition
from app.services.datasource_service import clear_datasource_metadata
from app.services.routine_lineage_service import rebuild_routine_sql_facts
from app.services.view_lineage_service import rebuild_view_sql_facts


CREATE_TABLE_PREFIX = re.compile(
    r"^\s*create\s+(?:or\s+replace\s+)?table\s+([A-Za-z0-9_.$#\"]+)\s*\(",
    re.IGNORECASE,
)
CREATE_VIEW_PREFIX = re.compile(
    r"^\s*create\s+(?:or\s+replace\s+)?(?:force\s+|editionable\s+|noneditionable\s+|force\s+editionable\s+|force\s+noneditionable\s+)?view\s+([A-Za-z0-9_.$#\"]+)\s+as\b",
    re.IGNORECASE,
)
CREATE_ROUTINE_PREFIX = re.compile(
    r"^\s*create\s+(?:or\s+replace\s+)?(procedure|function)\s+([A-Za-z0-9_.$#\"]+)",
    re.IGNORECASE,
)
COMMENT_ON_TABLE_PATTERN = re.compile(
    r"comment\s+on\s+table\s+([A-Za-z0-9_.$#\"]+)\s+is\s+'((?:''|[^'])*)'",
    re.IGNORECASE,
)
COMMENT_ON_COLUMN_PATTERN = re.compile(
    r"comment\s+on\s+column\s+([A-Za-z0-9_.$#\"]+)\.([A-Za-z0-9_.$#\"]+)\s+is\s+'((?:''|[^'])*)'",
    re.IGNORECASE,
)
INLINE_COLUMN_COMMENT_PATTERN = re.compile(
    r"\bcomment\s+'((?:''|[^'])*)'",
    re.IGNORECASE,
)
STATEMENT_START_PATTERN = re.compile(
    r"^\s*(create\s+(?:or\s+replace\s+)?(?:(?:force|editionable|noneditionable)\s+)*(?:table|view|procedure|function)\b|comment\s+on\s+(?:table|column)\b)",
    re.IGNORECASE,
)


@dataclass
class ParsedColumn:
    name: str
    type: str
    comment: str | None = None


@dataclass
class ParsedTable:
    owner: str
    name: str
    original_comment: str | None
    columns: list[ParsedColumn] = field(default_factory=list)


@dataclass
class ParsedView:
    owner: str
    name: str
    definition_text: str
    original_comment: str | None = None


@dataclass
class ParsedRoutine:
    owner: str
    name: str
    routine_type: str
    definition_text: str


@dataclass
class ParsedSqlImport:
    tables: list[ParsedTable] = field(default_factory=list)
    views: list[ParsedView] = field(default_factory=list)
    routines: list[ParsedRoutine] = field(default_factory=list)


def _decode_upload_bytes(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("latin-1")


async def create_sql_import_batch(
    session: Session,
    datasource: DataSource,
    files: list[UploadFile],
) -> DataSource:
    if datasource.source_mode != SourceMode.SQL_FILE:
        raise HTTPException(status_code=400, detail="只有 SQL 文件模式支持上传 SQL")

    valid_files = [file for file in files if file.filename]
    if not valid_files:
        raise HTTPException(status_code=400, detail="SQL 文件模式必须上传至少一个 .sql 文件")

    for file in valid_files:
        if not file.filename.lower().endswith(".sql"):
            raise HTTPException(status_code=400, detail="仅支持上传 .sql 文件")

    latest_batch = session.exec(
        select(SqlImportBatch)
        .where(SqlImportBatch.datasource_id == datasource.id)
        .order_by(SqlImportBatch.batch_no.desc())
    ).first()
    next_batch_no = 1 if latest_batch is None else latest_batch.batch_no + 1
    now = datetime.now()

    batch = SqlImportBatch(
        datasource_id=datasource.id,
        batch_no=next_batch_no,
        status=SqlImportBatchStatus.UPLOADED,
        message=f"已上传 {len(valid_files)} 个 SQL 文件",
        created_at=now,
        updated_at=now,
    )
    session.add(batch)
    session.flush()

    for index, file in enumerate(valid_files):
        content = _decode_upload_bytes(await file.read())
        session.add(
            SqlImportFile(
                batch_id=batch.id,
                file_name=file.filename,
                file_content=content,
                sort_order=index,
            )
        )

    datasource.source_status = SourceStatus.FILE_UPLOADED
    datasource.source_message = batch.message
    datasource.source_file_count = len(valid_files)
    datasource.updated_at = now
    session.add(datasource)
    session.commit()
    session.refresh(datasource)
    return datasource


def parse_latest_sql_import_batch(session: Session, datasource: DataSource) -> dict:
    if datasource.source_mode != SourceMode.SQL_FILE:
        raise HTTPException(status_code=400, detail="只有 SQL 文件模式支持解析 SQL")

    batch = session.exec(
        select(SqlImportBatch)
        .where(SqlImportBatch.datasource_id == datasource.id)
        .order_by(SqlImportBatch.batch_no.desc())
    ).first()
    if batch is None:
        raise HTTPException(status_code=400, detail="当前数据源还没有上传 SQL 文件")

    files = session.exec(
        select(SqlImportFile)
        .where(SqlImportFile.batch_id == batch.id)
        .order_by(SqlImportFile.sort_order, SqlImportFile.id)
    ).all()
    if not files:
        raise HTTPException(status_code=400, detail="当前批次没有可解析的 SQL 文件")

    now = datetime.now()
    datasource.source_status = SourceStatus.SYNCING
    datasource.source_message = "正在解析 SQL 文件并同步对象"
    datasource.updated_at = now
    batch.status = SqlImportBatchStatus.PROCESSING
    batch.message = "正在解析 SQL 文件并同步对象"
    batch.updated_at = now
    session.add(datasource)
    session.add(batch)
    session.commit()

    try:
        parsed = ParsedSqlImport()
        for file in files:
            merge_parsed_import(parsed, parse_sql_text(file.file_content, datasource))

        clear_datasource_metadata(session, datasource.id)

        table_models: list[SchemaTable] = []
        routine_models: list[RoutineDefinition] = []
        view_models: list[ViewDefinition] = []
        for table in parsed.tables:
            table_model = SchemaTable(
                datasource_id=datasource.id,
                name=table.name,
                original_comment=table.original_comment,
            )
            session.add(table_model)
            session.flush()
            for column in table.columns:
                session.add(
                    SchemaField(
                        table_id=table_model.id,
                        name=column.name,
                        type=column.type,
                        original_comment=column.comment,
                    )
                )
            table_models.append(table_model)

        for view in parsed.views:
            view_model = ViewDefinition(
                datasource_id=datasource.id,
                owner=view.owner,
                name=view.name,
                definition_text=view.definition_text,
                original_comment=view.original_comment,
                created_at=now,
                updated_at=now,
            )
            session.add(view_model)
            view_models.append(view_model)

        for routine in parsed.routines:
            routine_model = RoutineDefinition(
                datasource_id=datasource.id,
                owner=routine.owner,
                name=routine.name,
                routine_type=routine.routine_type,
                definition_text=routine.definition_text,
                created_at=now,
                updated_at=now,
            )
            session.add(routine_model)
            routine_models.append(routine_model)

        session.flush()

        rebuild_view_sql_facts(session, datasource_id=datasource.id, views=view_models)
        rebuild_routine_sql_facts(
            session,
            datasource_id=datasource.id,
            routines=routine_models,
        )

        batch.status = SqlImportBatchStatus.PARSED
        batch.message = (
            f"解析成功：{len(parsed.tables)} 张表，"
            f"{len(parsed.views)} 个视图，{len(parsed.routines)} 个存储过程/函数"
        )
        batch.updated_at = datetime.now()
        datasource.source_status = SourceStatus.PARSE_SUCCESS
        datasource.source_message = batch.message
        datasource.updated_at = datetime.now()
        session.add(batch)
        session.add(datasource)
        session.commit()
        return {
            "success": True,
            "message": batch.message,
            "tables": len(parsed.tables),
            "views": len(parsed.views),
            "routines": len(parsed.routines),
        }
    except Exception as exc:
        session.rollback()
        batch = session.get(SqlImportBatch, batch.id)
        datasource = session.get(DataSource, datasource.id)
        if batch is not None:
            batch.status = SqlImportBatchStatus.FAILED
            batch.message = str(exc)
            batch.updated_at = datetime.now()
            session.add(batch)
        if datasource is not None:
            datasource.source_status = SourceStatus.PARSE_FAILED
            datasource.source_message = str(exc)
            datasource.updated_at = datetime.now()
            session.add(datasource)
        session.commit()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def merge_parsed_import(target: ParsedSqlImport, fragment: ParsedSqlImport) -> None:
    target.tables.extend(fragment.tables)
    target.views.extend(fragment.views)
    target.routines.extend(fragment.routines)


def parse_sql_text(content: str, datasource: DataSource) -> ParsedSqlImport:
    statements = extract_sql_statements(content)
    parsed = ParsedSqlImport()
    table_map: dict[str, ParsedTable] = {}

    for statement in statements:
        table_match = CREATE_TABLE_PREFIX.match(statement)
        if table_match:
            table = parse_create_table(statement, datasource)
            table_map[table.name.lower()] = table
            parsed.tables.append(table)
            continue

        view_match = CREATE_VIEW_PREFIX.match(statement)
        if view_match:
            parsed.views.append(parse_create_view(statement, datasource))
            continue

        routine_match = CREATE_ROUTINE_PREFIX.match(statement)
        if routine_match:
            parsed.routines.append(parse_create_routine(statement, datasource))

    for table_name, comment in COMMENT_ON_TABLE_PATTERN.findall(content):
        normalized = normalize_identifier(table_name)
        if normalized in table_map:
            table_map[normalized].original_comment = unescape_sql_string(comment)

    for table_name, column_name, comment in COMMENT_ON_COLUMN_PATTERN.findall(content):
        normalized_table = normalize_identifier(table_name)
        normalized_column = normalize_identifier(column_name)
        table = table_map.get(normalized_table)
        if table is None:
            continue
        for column in table.columns:
            if column.name.lower() == normalized_column:
                column.comment = unescape_sql_string(comment)
                break

    return parsed


def parse_create_table(statement: str, datasource: DataSource) -> ParsedTable:
    match = CREATE_TABLE_PREFIX.match(statement)
    if not match:
        raise ValueError("无法识别 CREATE TABLE 语句")
    owner, table_name = split_owner_and_name(match.group(1), datasource)
    start_index = statement.find("(", match.end() - 1)
    end_index = find_matching_paren(statement, start_index)
    columns_sql = statement[start_index + 1 : end_index]
    table = ParsedTable(owner=owner, name=table_name, original_comment=None)

    for segment in split_top_level(columns_sql, ","):
        column = parse_column_definition(segment)
        if column is not None:
            table.columns.append(column)
    return table


def parse_create_view(statement: str, datasource: DataSource) -> ParsedView:
    match = CREATE_VIEW_PREFIX.match(statement)
    if not match:
        raise ValueError("无法识别 CREATE VIEW 语句")
    owner, view_name = split_owner_and_name(match.group(1), datasource)
    return ParsedView(
        owner=owner,
        name=view_name,
        definition_text=statement.strip(),
    )


def parse_create_routine(statement: str, datasource: DataSource) -> ParsedRoutine:
    match = CREATE_ROUTINE_PREFIX.match(statement)
    if not match:
        raise ValueError("无法识别 CREATE PROCEDURE/FUNCTION 语句")
    routine_type = match.group(1).upper()
    owner, routine_name = split_owner_and_name(match.group(2), datasource)
    return ParsedRoutine(
        owner=owner,
        name=routine_name,
        routine_type=routine_type,
        definition_text=statement.strip().rstrip("/").strip(),
    )


def parse_column_definition(segment: str) -> ParsedColumn | None:
    text = segment.strip()
    if not text:
        return None
    lowered = text.lower()
    if lowered.startswith(
        ("constraint ", "primary key", "unique ", "foreign key", "check ", "key ", "index ")
    ):
        return None

    parts = text.split(None, 1)
    if len(parts) < 2:
        return None

    column_name = normalize_identifier(parts[0])
    remainder = parts[1].strip()
    comment_match = INLINE_COLUMN_COMMENT_PATTERN.search(remainder)
    comment = None
    if comment_match:
        comment = unescape_sql_string(comment_match.group(1))
        remainder = INLINE_COLUMN_COMMENT_PATTERN.sub("", remainder).strip()
    remainder = re.sub(r"\s+", " ", remainder).strip().rstrip(",")
    if not remainder:
        return None
    return ParsedColumn(name=column_name, type=remainder, comment=comment)


def extract_sql_statements(content: str) -> list[str]:
    statements: list[str] = []
    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    current: list[str] = []
    in_routine = False
    paren_depth = 0
    in_single_quote = False

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not current and not stripped:
            continue

        if not current:
            if not STATEMENT_START_PATTERN.match(stripped):
                continue
            in_routine = bool(CREATE_ROUTINE_PREFIX.match(stripped))
        current.append(line)
        paren_depth, in_single_quote = update_parse_state(line, paren_depth, in_single_quote)

        if in_routine:
            if stripped == "/":
                statements.append("\n".join(current).strip())
                current = []
                in_routine = False
                paren_depth = 0
                in_single_quote = False
            continue

        if stripped.endswith(";") and paren_depth == 0 and not in_single_quote:
            statements.append("\n".join(current).strip())
            current = []

    if current:
        statements.append("\n".join(current).strip())

    return [statement for statement in statements if statement]


def update_parse_state(line: str, paren_depth: int, in_single_quote: bool) -> tuple[int, bool]:
    idx = 0
    while idx < len(line):
        char = line[idx]
        if char == "'":
            if in_single_quote and idx + 1 < len(line) and line[idx + 1] == "'":
                idx += 2
                continue
            in_single_quote = not in_single_quote
        elif not in_single_quote:
            if char == "(":
                paren_depth += 1
            elif char == ")" and paren_depth > 0:
                paren_depth -= 1
        idx += 1
    return paren_depth, in_single_quote


def split_top_level(text: str, delimiter: str) -> list[str]:
    segments: list[str] = []
    current: list[str] = []
    paren_depth = 0
    in_single_quote = False

    for char in text:
        if char == "'":
            in_single_quote = not in_single_quote
        elif not in_single_quote:
            if char == "(":
                paren_depth += 1
            elif char == ")" and paren_depth > 0:
                paren_depth -= 1
            elif char == delimiter and paren_depth == 0:
                segments.append("".join(current))
                current = []
                continue
        current.append(char)

    if current:
        segments.append("".join(current))
    return segments


def find_matching_paren(text: str, start_index: int) -> int:
    if start_index < 0:
        raise ValueError("CREATE TABLE 缺少字段定义括号")
    depth = 0
    in_single_quote = False
    for index in range(start_index, len(text)):
        char = text[index]
        if char == "'":
            if in_single_quote and index + 1 < len(text) and text[index + 1] == "'":
                continue
            in_single_quote = not in_single_quote
        elif not in_single_quote:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return index
    raise ValueError("CREATE TABLE 字段括号未正确闭合")


def split_owner_and_name(identifier: str, datasource: DataSource) -> tuple[str, str]:
    cleaned = identifier.strip().strip('"')
    if "." in cleaned:
        owner, name = cleaned.rsplit(".", 1)
        return owner.strip('"'), name.strip('"')
    owner = (datasource.database or datasource.name or "FILE_IMPORT").strip()
    return owner, cleaned


def normalize_identifier(identifier: str) -> str:
    return identifier.strip().strip('"').split(".")[-1].lower()


def unescape_sql_string(value: str) -> str:
    return value.replace("''", "'")
