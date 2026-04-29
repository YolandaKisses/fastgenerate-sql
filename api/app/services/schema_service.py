import sqlalchemy
from sqlmodel import Session, select
from app.models.datasource import DataSource, DataSourceStatus
from app.models.schema import SchemaTable, SchemaField
from fastapi import HTTPException

def sync_schema_for_datasource(session: Session, ds: DataSource):
    try:
        if not ds.database:
            raise ValueError("数据库名 (Database/Schema) 不能为空，否则无法拉取表结构")
            
        if ds.db_type == "postgresql":
            url = f"postgresql://{ds.username}:{ds.password}@{ds.host}:{ds.port}/{ds.database}"
        elif ds.db_type == "mysql":
            url = f"mysql+pymysql://{ds.username}:{ds.password}@{ds.host}:{ds.port}/{ds.database}"
        elif ds.db_type == "oracle":
            url = f"oracle+cx_oracle://{ds.username}:{ds.password}@{ds.host}:{ds.port}/?service_name={ds.database}"
        else:
            raise ValueError(f"Unsupported db_type: {ds.db_type}")
            
        engine = sqlalchemy.create_engine(url, connect_args={"connect_timeout": 10})
        inspector = sqlalchemy.inspect(engine)
        
        # 获取现有表，以保留用户自定义的备注
        existing_tables = session.exec(select(SchemaTable).where(SchemaTable.datasource_id == ds.id)).all()
        table_map = {t.name: t for t in existing_tables}
        
        table_names = inspector.get_table_names()
        
        for t_name in table_names:
            # 兼容不同方言获取注释
            try:
                comment = inspector.get_table_comment(t_name).get("text", "")
            except:
                comment = ""
            
            if t_name in table_map:
                table_obj = table_map[t_name]
                table_obj.original_comment = comment
                session.add(table_obj)
            else:
                table_obj = SchemaTable(
                    datasource_id=ds.id,
                    name=t_name,
                    original_comment=comment
                )
                session.add(table_obj)
            
        session.commit()
        
        # 同步字段
        synced_tables = session.exec(select(SchemaTable).where(SchemaTable.datasource_id == ds.id)).all()
        
        for t_obj in synced_tables:
            # 只同步目前数据库真实存在的表
            if t_obj.name not in table_names:
                continue
                
            existing_fields = session.exec(select(SchemaField).where(SchemaField.table_id == t_obj.id)).all()
            field_map = {f.name: f for f in existing_fields}
            
            columns = inspector.get_columns(t_obj.name)
            for col in columns:
                c_name = col["name"]
                c_type = str(col["type"])
                c_comment = col.get("comment", "") or ""
                
                if c_name in field_map:
                    f_obj = field_map[c_name]
                    f_obj.type = c_type
                    f_obj.original_comment = c_comment
                    session.add(f_obj)
                else:
                    f_obj = SchemaField(
                        table_id=t_obj.id,
                        name=c_name,
                        type=c_type,
                        original_comment=c_comment
                    )
                    session.add(f_obj)
                    
        ds.status = DataSourceStatus.READY
        session.add(ds)
        session.commit()
        
        return {"success": True, "message": f"成功同步了 {len(table_names)} 张表"}
    except Exception as e:
        ds.status = DataSourceStatus.SYNC_FAILED
        session.add(ds)
        session.commit()
        return {"success": False, "message": str(e)}

def get_tables(session: Session, datasource_id: int):
    return session.exec(select(SchemaTable).where(SchemaTable.datasource_id == datasource_id)).all()

def get_fields(session: Session, table_id: int):
    return session.exec(select(SchemaField).where(SchemaField.table_id == table_id)).all()

def update_field_remark(session: Session, field_id: int, remark: str):
    field = session.get(SchemaField, field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    field.supplementary_comment = remark
    session.add(field)
    session.commit()
    session.refresh(field)
    return field
