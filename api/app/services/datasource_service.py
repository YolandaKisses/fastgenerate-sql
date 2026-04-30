from sqlmodel import Session, select
from app.models.datasource import DataSource, DataSourceCreate, DataSourceUpdate, DataSourceStatus
from app.models.schema import SchemaTable, SchemaField
from fastapi import HTTPException
import sqlalchemy
from urllib.parse import quote_plus

CONNECTION_FIELDS = {"db_type", "host", "port", "database", "username", "password"}


def build_database_url(ds: DataSource) -> str:
    username = quote_plus(ds.username)
    password = quote_plus(ds.password)
    if ds.db_type == "postgresql":
        return f"postgresql://{username}:{password}@{ds.host}:{ds.port}/{ds.database}"
    if ds.db_type == "mysql":
        return f"mysql+pymysql://{username}:{password}@{ds.host}:{ds.port}/{ds.database}"
    if ds.db_type == "oracle":
        return f"oracle+oracledb://{username}:{password}@{ds.host}:{ds.port}/?service_name={ds.database}"
    raise ValueError(f"Unsupported db_type: {ds.db_type}")


def build_connect_args(ds: DataSource, timeout_seconds: int) -> dict:
    if ds.db_type in {"postgresql", "mysql"}:
        return {"connect_timeout": timeout_seconds}
    if ds.db_type == "oracle":
        return {"tcp_connect_timeout": timeout_seconds}
    return {}


def create_datasource(session: Session, ds_in: DataSourceCreate) -> DataSource:
    ds = DataSource.model_validate(ds_in)
    session.add(ds)
    session.commit()
    session.refresh(ds)
    return ds

def get_datasources(session: Session) -> list[DataSource]:
    return session.exec(select(DataSource)).all()

def update_datasource(session: Session, ds_id: int, ds_in: DataSourceUpdate) -> DataSource:
    ds = session.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource not found")

    ds_data = ds_in.model_dump(exclude_unset=True)
    touched_connection_fields = False
    for key, value in ds_data.items():
        if key in CONNECTION_FIELDS and getattr(ds, key) != value:
            touched_connection_fields = True
        setattr(ds, key, value)

    if touched_connection_fields and "status" not in ds_data:
        ds.status = DataSourceStatus.STALE

    session.add(ds)
    session.commit()
    session.refresh(ds)
    return ds

def test_connection(ds: DataSource) -> dict:
    try:
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
    if "access denied" in lowered or "authentication failed" in lowered or "password authentication failed" in lowered:
        return {"success": False, "reason": "auth_failed", "message": "测试连接失败：认证失败，请检查用户名和密码"}
    if "unknown database" in lowered or "database does not exist" in lowered or "service_name" in lowered and "does not exist" in lowered:
        return {"success": False, "reason": "database_not_found", "message": "测试连接失败：数据库不存在，请检查数据库名或服务名"}
    if "timeout" in lowered or "could not connect" in lowered or "connection refused" in lowered or "name or service not known" in lowered:
        return {"success": False, "reason": "host_unreachable", "message": "测试连接失败：主机不可达，请检查地址、端口和网络"}
    if "permission denied" in lowered or "insufficient privilege" in lowered or "not authorized" in lowered:
        return {"success": False, "reason": "metadata_permission_denied", "message": "测试连接失败：缺少访问元数据所需权限"}
    return {"success": False, "reason": "unknown", "message": message}


def delete_datasource(session: Session, ds_id: int) -> dict:
    ds = session.get(DataSource, ds_id)
    if not ds:
        raise HTTPException(status_code=404, detail="DataSource not found")

    tables = session.exec(select(SchemaTable).where(SchemaTable.datasource_id == ds_id)).all()
    table_ids = [table.id for table in tables if table.id is not None]
    if table_ids:
        fields = session.exec(select(SchemaField).where(SchemaField.table_id.in_(table_ids))).all()
        for field in fields:
            session.delete(field)

    for table in tables:
        session.delete(table)

    session.delete(ds)
    session.commit()
    return {"success": True}
