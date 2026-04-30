from sqlmodel import Session, select
from app.models.datasource import DataSource, DataSourceCreate, DataSourceUpdate, DataSourceStatus
from app.models.schema import SchemaTable, SchemaField
from fastapi import HTTPException
import sqlalchemy

CONNECTION_FIELDS = {"db_type", "host", "port", "database", "username", "password"}


def build_database_url(ds: DataSource) -> str:
    if ds.db_type == "postgresql":
        return f"postgresql://{ds.username}:{ds.password}@{ds.host}:{ds.port}/{ds.database}"
    if ds.db_type == "mysql":
        return f"mysql+pymysql://{ds.username}:{ds.password}@{ds.host}:{ds.port}/{ds.database}"
    if ds.db_type == "oracle":
        return f"oracle+oracledb://{ds.username}:{ds.password}@{ds.host}:{ds.port}/?service_name={ds.database}"
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
            return {"success": False, "message": "测试连接失败：必须填写数据库名 (Database/Schema)"}

        url = build_database_url(ds)
        engine = sqlalchemy.create_engine(url, connect_args=build_connect_args(ds, 5))
        with engine.connect() as conn:
            pass
        return {"success": True, "message": "Connection successful"}
    except Exception as e:
        return {"success": False, "message": str(e)}


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
