from sqlmodel import Session, select
from app.models.datasource import DataSource, DataSourceCreate, DataSourceUpdate, DataSourceStatus
from fastapi import HTTPException
import sqlalchemy

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
    for key, value in ds_data.items():
        setattr(ds, key, value)
    
    session.add(ds)
    session.commit()
    session.refresh(ds)
    return ds

def test_connection(ds: DataSource) -> dict:
    try:
        if not ds.database:
            return {"success": False, "message": "测试连接失败：必须填写数据库名 (Database/Schema)"}
            
        if ds.db_type == "postgresql":
            url = f"postgresql://{ds.username}:{ds.password}@{ds.host}:{ds.port}/{ds.database}"
        elif ds.db_type == "mysql":
            url = f"mysql+pymysql://{ds.username}:{ds.password}@{ds.host}:{ds.port}/{ds.database}"
        else:
            return {"success": False, "message": f"Unsupported db_type: {ds.db_type}"}
            
        # 简单测试连接
        engine = sqlalchemy.create_engine(url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            pass
        return {"success": True, "message": "Connection successful"}
    except Exception as e:
        return {"success": False, "message": str(e)}
