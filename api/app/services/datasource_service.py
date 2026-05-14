from datetime import datetime

from sqlmodel import Session, select
from app.models.datasource import (
    DataSource,
    DataSourceCreate,
    DataSourceStatus,
    DataSourceUpdate,
    SourceMode,
    SourceStatus,
)
from app.models.routine import RoutineDefinition, RoutineSqlFact
from app.models.schema import SchemaTable, SchemaField
from app.models.sql_import import SqlImportBatch, SqlImportFile
from app.models.view import ViewDefinition, ViewSqlFact
from app.core.security import (
    decrypt_datasource_password,
    encrypt_datasource_password,
    is_encrypted_datasource_password,
)
from fastapi import HTTPException
import sqlalchemy
from urllib.parse import quote_plus

CONNECTION_FIELDS = {"db_type", "host", "port", "database", "username", "password"}
CONNECTION_REQUIRED_FIELDS = ("host", "port", "database", "username", "password")
SQL_FILE_PLACEHOLDERS = {
    "host": "",
    "port": 0,
    "database": "",
    "username": "",
    "password": "",
}


def build_database_url(ds: DataSource) -> str:
    missing = [
        field_name
        for field_name in CONNECTION_REQUIRED_FIELDS
        if not getattr(ds, field_name, None)
    ]
    if missing:
        raise ValueError(f"连接型数据源缺少必要字段: {', '.join(missing)}")
    username = quote_plus(ds.username)
    password = quote_plus(decrypt_datasource_password(ds.password))
    if ds.db_type == "postgresql":
        return f"postgresql://{username}:{password}@{ds.host}:{ds.port}/{ds.database}"
    if ds.db_type == "mysql":
        return f"mysql+pymysql://{username}:{password}@{ds.host}:{ds.port}/{ds.database}"
    if ds.db_type == "oracle":
        # Oracle 支持两种连接方式：SID 和 Service Name
        # 约定：如果数据库名以 ':' 开头，则按 SID 方式连接 (使用 ?sid= 参数)
        # 否则按 Service Name 方式连接 (直接拼接在路径后，这是 DBeaver 等工具的常用格式)
        if ds.database.startswith(":"):
            sid = ds.database[1:].strip()
            return f"oracle+oracledb://{username}:{password}@{ds.host}:{ds.port}/?sid={sid}"
        
        # 针对 orclpdb 这种 Service Name，显式使用 ?service_name= 参数
        # 这能避免 Thick 模式下将路径误认为 SID (导致 ORA-12505)
        return f"oracle+oracledb://{username}:{password}@{ds.host}:{ds.port}/?service_name={ds.database.strip()}"
    raise ValueError(f"Unsupported db_type: {ds.db_type}")


def build_connect_args(ds: DataSource, timeout_seconds: int) -> dict:
    if ds.db_type in {"postgresql", "mysql"}:
        return {"connect_timeout": timeout_seconds}
    if ds.db_type == "oracle":
        return {"tcp_connect_timeout": timeout_seconds}
    return {}


def validate_datasource_payload(ds_in: DataSourceCreate | DataSourceUpdate, *, existing: DataSource | None = None) -> None:
    source_mode = getattr(ds_in, "source_mode", None) or getattr(existing, "source_mode", SourceMode.CONNECTION)
    if source_mode == SourceMode.SQL_FILE:
        if not getattr(ds_in, "name", None) and existing is None:
            raise HTTPException(status_code=400, detail="SQL 文件模式必须填写数据源名称")
        if not getattr(ds_in, "db_type", None) and existing is None:
            raise HTTPException(status_code=400, detail="SQL 文件模式必须选择数据库类型")
        return

    missing = []
    for field_name in CONNECTION_REQUIRED_FIELDS:
        incoming = getattr(ds_in, field_name, None)
        if incoming is None and existing is not None:
            incoming = getattr(existing, field_name, None)
        if incoming in (None, ""):
            missing.append(field_name)

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"连接型数据源缺少必要字段: {', '.join(missing)}",
        )


def normalize_sql_file_fields(ds_data: dict) -> dict:
    normalized = dict(ds_data)
    for key, value in SQL_FILE_PLACEHOLDERS.items():
        normalized[key] = value
    return normalized


def create_datasource(session: Session, ds_in: DataSourceCreate, user_id: str = "system") -> DataSource:
    validate_datasource_payload(ds_in)
    ds_data = ds_in.model_dump()
    ds_data["user_id"] = user_id
    if ds_data.get("source_mode") == SourceMode.SQL_FILE:
        ds_data = normalize_sql_file_fields(ds_data)
    ds = DataSource.model_validate(ds_data)
    if ds.source_mode == SourceMode.SQL_FILE:
        ds.host = SQL_FILE_PLACEHOLDERS["host"]
        ds.port = SQL_FILE_PLACEHOLDERS["port"]
        ds.database = SQL_FILE_PLACEHOLDERS["database"]
        ds.username = SQL_FILE_PLACEHOLDERS["username"]
        ds.password = SQL_FILE_PLACEHOLDERS["password"]
        ds.source_status = SourceStatus.DRAFT
        ds.status = DataSourceStatus.DRAFT
    elif ds.password:
        ds.password = encrypt_datasource_password(ds.password)
    session.add(ds)
    session.commit()
    session.refresh(ds)
    return ds

def get_datasources(session: Session, user_id: str) -> list[DataSource]:
    return session.exec(select(DataSource).where(DataSource.user_id == user_id)).all()


def encrypt_existing_datasource_passwords(session: Session) -> int:
    datasources = session.exec(select(DataSource)).all()
    migrated_count = 0
    for ds in datasources:
        if ds.password and not is_encrypted_datasource_password(ds.password):
            ds.password = encrypt_datasource_password(ds.password)
            session.add(ds)
            migrated_count += 1

    if migrated_count:
        session.commit()
    return migrated_count

def update_datasource(session: Session, ds_id: int, ds_in: DataSourceUpdate, user_id: str | None = None) -> DataSource:
    ds = session.get(DataSource, ds_id)
    if not ds or (user_id is not None and ds.user_id != user_id):
        raise HTTPException(status_code=404, detail="DataSource not found")

    validate_datasource_payload(ds_in, existing=ds)
    ds_data = ds_in.model_dump(exclude_unset=True)
    if ds_data.get("password") is None:
        ds_data.pop("password", None)
    touched_connection_fields = False
    for key, value in ds_data.items():
        next_value = encrypt_datasource_password(value) if key == "password" else value
        comparable_current = decrypt_datasource_password(ds.password) if key == "password" else getattr(ds, key)
        if key in CONNECTION_FIELDS and comparable_current != value:
            touched_connection_fields = True
        setattr(ds, key, next_value)

    if ds.source_mode == SourceMode.SQL_FILE:
        ds.host = SQL_FILE_PLACEHOLDERS["host"]
        ds.port = SQL_FILE_PLACEHOLDERS["port"]
        ds.database = SQL_FILE_PLACEHOLDERS["database"]
        ds.username = SQL_FILE_PLACEHOLDERS["username"]
        ds.password = SQL_FILE_PLACEHOLDERS["password"]
    elif touched_connection_fields and "status" not in ds_data:
        ds.status = DataSourceStatus.STALE
        ds.source_status = SourceStatus.DRAFT
    ds.updated_at = datetime.now()

    session.add(ds)
    session.commit()
    session.refresh(ds)
    return ds

def test_connection(ds: DataSource) -> dict:
    try:
        if ds.source_mode != SourceMode.CONNECTION:
            return {"success": False, "reason": "unsupported_mode", "message": "SQL 文件模式不支持测试连接"}
        if not ds.database:
            return {"success": False, "reason": "database_required", "message": "测试连接失败：必须填写数据库名 (Database/Schema)"}

        url = build_database_url(ds)
        engine = sqlalchemy.create_engine(url, connect_args=build_connect_args(ds, 5))
        try:
            with engine.connect() as conn:
                pass
        finally:
            engine.dispose()
        return {"success": True, "message": "Connection successful"}
    except Exception as e:
        return classify_connection_error(e)


def classify_connection_error(error: Exception) -> dict:
    message = str(error)
    lowered = message.lower()
    # 认证失败（含 Oracle ORA-01017）
    if ("access denied" in lowered or "authentication failed" in lowered
            or "password authentication failed" in lowered
            or "ora-01017" in lowered or "invalid username/password" in lowered):
        return {"success": False, "reason": "auth_failed", "message": "测试连接失败：认证失败，请检查用户名和密码"}
    # 数据库/服务名不存在（含 Oracle ORA-12514）
    if ("unknown database" in lowered or "database does not exist" in lowered
            or ("service_name" in lowered and "does not exist" in lowered)
            or "ora-12514" in lowered):
        return {"success": False, "reason": "database_not_found", "message": "测试连接失败：数据库不存在，请检查数据库名或服务名"}
    # 主机不可达（含 Oracle ORA-12541 / ORA-12543）
    if ("timeout" in lowered or "could not connect" in lowered
            or "connection refused" in lowered or "name or service not known" in lowered
            or "ora-12541" in lowered or "ora-12543" in lowered or "ora-12170" in lowered):
        return {"success": False, "reason": "host_unreachable", "message": "测试连接失败：主机不可达，请检查地址、端口和网络"}
    # 权限不足（含 Oracle ORA-01031）
    if ("permission denied" in lowered or "insufficient privilege" in lowered
            or "not authorized" in lowered or "ora-01031" in lowered):
        return {"success": False, "reason": "metadata_permission_denied", "message": "测试连接失败：缺少访问元数据所需权限"}
    # 密码验证器版本过低 (Oracle 11g 或 DPY-3015)
    if "dpy-3015" in lowered or "password verifier type" in lowered:
        return {"success": False, "reason": "unsupported_verifier", "message": "测试连接失败：当前 Oracle 密码验证器版本过低(11g)，Python Thin 模式不支持。请重新设置用户密码以升级验证器，或安装 Oracle Instant Client 并开启 Thick 模式。"}
    # 数据库版本过低 (Oracle 11g 或 DPY-3010)
    if "dpy-3010" in lowered or "database server version are not supported" in lowered:
        return {"success": False, "reason": "unsupported_version", "message": "测试连接失败：Oracle 数据库版本过低(11g或更老)，Python Thin 模式不支持。请安装 Oracle Instant Client 并开启 Thick 模式。"}
    return {"success": False, "reason": "unknown", "message": message}


def delete_datasource(session: Session, ds_id: int, user_id: str) -> dict:
    ds = session.get(DataSource, ds_id)
    if not ds or ds.user_id != user_id:
        raise HTTPException(status_code=404, detail="DataSource not found")

    clear_datasource_metadata(session, ds_id)

    batches = session.exec(select(SqlImportBatch).where(SqlImportBatch.datasource_id == ds_id)).all()
    batch_ids = [batch.id for batch in batches if batch.id is not None]
    if batch_ids:
        files = session.exec(select(SqlImportFile).where(SqlImportFile.batch_id.in_(batch_ids))).all()
        for file in files:
            session.delete(file)
    for batch in batches:
        session.delete(batch)

    session.delete(ds)
    session.commit()
    return {"success": True}


def clear_datasource_metadata(session: Session, ds_id: int) -> None:
    tables = session.exec(select(SchemaTable).where(SchemaTable.datasource_id == ds_id)).all()
    table_ids = [table.id for table in tables if table.id is not None]
    if table_ids:
        fields = session.exec(select(SchemaField).where(SchemaField.table_id.in_(table_ids))).all()
        for field in fields:
            session.delete(field)

    routines = session.exec(select(RoutineDefinition).where(RoutineDefinition.datasource_id == ds_id)).all()
    routine_facts = session.exec(select(RoutineSqlFact).where(RoutineSqlFact.datasource_id == ds_id)).all()
    views = session.exec(select(ViewDefinition).where(ViewDefinition.datasource_id == ds_id)).all()
    view_facts = session.exec(select(ViewSqlFact).where(ViewSqlFact.datasource_id == ds_id)).all()
    for fact in routine_facts:
        session.delete(fact)
    for fact in view_facts:
        session.delete(fact)
    for routine in routines:
        session.delete(routine)
    for view in views:
        session.delete(view)

    for table in tables:
        session.delete(table)
