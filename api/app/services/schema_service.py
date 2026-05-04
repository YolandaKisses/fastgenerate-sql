import sqlalchemy
from datetime import datetime
from pathlib import Path
from sqlmodel import Session, select
from app.models.datasource import DataSource, DataSourceStatus, SyncStatus
from app.models.schema import SchemaTable, SchemaField
from fastapi import HTTPException
from app.services.datasource_service import build_connect_args, build_database_url
from app.services import setting_service
from app.core.config import settings
from app.services.path_utils import sanitize_path_segment


def delete_table_note_if_exists(session: Session, ds: DataSource, table_name: str) -> None:
    vault_root = setting_service.get_setting(session, "obsidian_vault_root", settings.OBSIDIAN_VAULT_ROOT)
    if not vault_root:
        return

    note_path = (
        Path(vault_root)
        / sanitize_path_segment(ds.name)
        / "tables"
        / f"{sanitize_path_segment(table_name)}.md"
    )
    try:
        if note_path.exists():
            note_path.unlink()
    except OSError:
        # Schema 同步不能因为旧知识库文件清理失败而回滚元数据更新。
        pass

def sync_schema_for_datasource(session: Session, ds: DataSource):
    ds.sync_status = SyncStatus.SYNCING
    ds.last_sync_message = "正在同步 Schema"
    session.add(ds)
    session.commit()
    try:
        if not ds.database:
            raise ValueError("数据库名 (Database/Schema) 不能为空，否则无法拉取表结构")

        url = build_database_url(ds)
        engine = sqlalchemy.create_engine(url, connect_args=build_connect_args(ds, 10))
        inspector = sqlalchemy.inspect(engine)
        has_partial_failures = False

        # 获取现有表，以保留用户自定义的备注
        existing_tables = session.exec(select(SchemaTable).where(SchemaTable.datasource_id == ds.id)).all()
        table_map = {t.name: t for t in existing_tables}
        changed_table_notes: set[str] = set()

        table_names = inspector.get_table_names()
        current_table_names = set(table_names)
        if not table_names:
            ds.status = DataSourceStatus.SYNC_FAILED
            ds.sync_status = SyncStatus.SYNC_FAILED
            ds.last_sync_message = "同步结果为空，当前数据源没有可用表结构"
            ds.last_synced_at = datetime.now()
            session.add(ds)
            session.commit()
            return {"success": False, "message": ds.last_sync_message}

        for obsolete_table in existing_tables:
            if obsolete_table.name not in current_table_names:
                existing_fields = session.exec(
                    select(SchemaField).where(SchemaField.table_id == obsolete_table.id)
                ).all()
                for field in existing_fields:
                    session.delete(field)
                delete_table_note_if_exists(session, ds, obsolete_table.name)
                session.delete(obsolete_table)

        session.commit()

        for t_name in table_names:
            # 兼容不同方言获取注释
            try:
                comment = inspector.get_table_comment(t_name).get("text", "")
            except:
                comment = ""
                has_partial_failures = True

            if t_name in table_map:
                table_obj = table_map[t_name]
                if table_obj.original_comment != comment:
                    changed_table_notes.add(t_name)
                table_obj.original_comment = comment
                session.add(table_obj)
            else:
                changed_table_notes.add(t_name)
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
            if t_obj.name not in current_table_names:
                continue

            existing_fields = session.exec(select(SchemaField).where(SchemaField.table_id == t_obj.id)).all()
            field_map = {f.name: f for f in existing_fields}

            columns = inspector.get_columns(t_obj.name)
            current_field_names = {col.get("name") for col in columns if col.get("name")}
            existing_field_names = {field.name for field in existing_fields}
            if current_field_names != existing_field_names:
                changed_table_notes.add(t_obj.name)

            for obsolete_field in existing_fields:
                if obsolete_field.name not in current_field_names:
                    session.delete(obsolete_field)

            for col in columns:
                try:
                    c_name = col["name"]
                    c_type = str(col["type"])
                    c_comment = col.get("comment", "") or ""
                except Exception:
                    has_partial_failures = True
                    continue

                if c_name in field_map:
                    f_obj = field_map[c_name]
                    if f_obj.type != c_type or f_obj.original_comment != c_comment:
                        changed_table_notes.add(t_obj.name)
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

        for table_name in changed_table_notes:
            delete_table_note_if_exists(session, ds, table_name)

        ds.status = DataSourceStatus.CONNECTION_OK
        ds.sync_status = SyncStatus.NEVER_SYNCED
        ds.last_sync_message = (
            f"Schema 已同步 {len(table_names)} 张表，请继续同步到知识库"
            if not has_partial_failures
            else f"Schema 部分同步完成，共同步 {len(table_names)} 张表，请检查后同步到知识库"
        )
        ds.last_synced_at = datetime.now()
        session.add(ds)
        session.commit()

        return {"success": True, "message": ds.last_sync_message}
    except Exception as e:
        ds.status = DataSourceStatus.SYNC_FAILED
        ds.sync_status = SyncStatus.SYNC_FAILED
        ds.last_sync_message = str(e)
        ds.last_synced_at = datetime.now()
        session.add(ds)
        session.commit()
        return {"success": False, "message": str(e)}

def get_tables(session: Session, datasource_id: int):
    return session.exec(select(SchemaTable).where(SchemaTable.datasource_id == datasource_id)).all()

def get_fields(session: Session, table_id: int):
    return session.exec(select(SchemaField).where(SchemaField.table_id == table_id)).all()

def update_table_remark(session: Session, table_id: int, remark: str):
    table = session.get(SchemaTable, table_id)
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    table.supplementary_comment = remark
    session.add(table)
    session.commit()
    session.refresh(table)
    return table

def update_field_remark(session: Session, field_id: int, remark: str):
    field = session.get(SchemaField, field_id)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    field.supplementary_comment = remark
    session.add(field)
    session.commit()
    session.refresh(field)
    return field
