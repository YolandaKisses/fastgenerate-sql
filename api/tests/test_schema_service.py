from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine, select

from app.models.datasource import DataSource, DataSourceStatus, SyncStatus
from app.models.schema import SchemaField, SchemaTable
from app.models.setting import RuntimeSetting
from app.services import schema_service


class FakeInspector:
    def get_table_names(self):
        return ["kept_table"]

    def get_table_comment(self, table_name):
        return {"text": "new original table comment"}

    def get_columns(self, table_name):
        return [
            {
                "name": "kept_field",
                "type": "VARCHAR(32)",
                "comment": "new original field comment",
            },
            {
                "name": "new_field",
                "type": "INTEGER",
                "comment": "new field comment",
            },
        ]


def test_schema_resync_removes_deleted_tables_fields_and_stale_knowledge_files(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    vault_root = tmp_path / "vault"
    tables_dir = vault_root / "demo" / "tables"
    tables_dir.mkdir(parents=True)
    deleted_note = tables_dir / "deleted_table.md"
    kept_note = tables_dir / "kept_table.md"
    deleted_note.write_text("stale table note", encoding="utf-8")
    kept_note.write_text("existing table note", encoding="utf-8")

    monkeypatch.setattr(schema_service.sqlalchemy, "create_engine", lambda *args, **kwargs: object())
    monkeypatch.setattr(schema_service.sqlalchemy, "inspect", lambda _engine: FakeInspector())
    monkeypatch.setattr(schema_service.settings, "WIKI_ROOT", str(vault_root))

    with Session(engine) as session:
        ds = DataSource(
            name="demo",
            db_type="mysql",
            host="localhost",
            port=3306,
            database="demo",
            username="root",
            password="secret",
            status=DataSourceStatus.CONNECTION_OK,
            sync_status=SyncStatus.SYNC_SUCCESS,
        )
        session.add(ds)

        session.commit()
        session.refresh(ds)

        kept_table = SchemaTable(
            datasource_id=ds.id,
            name="kept_table",
            original_comment="old original table comment",
            supplementary_comment="keep local table remark",
        )
        deleted_table = SchemaTable(
            datasource_id=ds.id,
            name="deleted_table",
            original_comment="deleted",
            supplementary_comment="delete me",
        )
        session.add(kept_table)
        session.add(deleted_table)
        session.commit()
        session.refresh(kept_table)
        session.refresh(deleted_table)
        session.add(
            SchemaField(
                table_id=kept_table.id,
                name="kept_field",
                type="TEXT",
                original_comment="old original field comment",
                supplementary_comment="keep local field remark",
            )
        )
        session.add(
            SchemaField(
                table_id=kept_table.id,
                name="removed_field",
                type="TEXT",
                original_comment="removed",
                supplementary_comment="remove me",
            )
        )
        session.add(
            SchemaField(
                table_id=deleted_table.id,
                name="deleted_table_field",
                type="TEXT",
            )
        )
        session.commit()

        result = schema_service.sync_schema_for_datasource(session, ds)

        assert result["success"] is True
        session.refresh(ds)
        assert ds.status == DataSourceStatus.CONNECTION_OK
        assert ds.sync_status == SyncStatus.NEVER_SYNCED

        table_names = {
            table.name
            for table in session.exec(select(SchemaTable).where(SchemaTable.datasource_id == ds.id)).all()
        }
        assert table_names == {"kept_table"}

        refreshed_table = session.exec(select(SchemaTable).where(SchemaTable.name == "kept_table")).one()
        assert refreshed_table.original_comment == "new original table comment"
        assert refreshed_table.supplementary_comment == "keep local table remark"

        fields = session.exec(select(SchemaField).where(SchemaField.table_id == refreshed_table.id)).all()
        fields_by_name = {field.name: field for field in fields}
        assert set(fields_by_name) == {"kept_field", "new_field"}
        assert fields_by_name["kept_field"].original_comment == "new original field comment"
        assert fields_by_name["kept_field"].supplementary_comment == "keep local field remark"
        assert fields_by_name["new_field"].original_comment == "new field comment"

        assert not deleted_note.exists()
        assert not kept_note.exists()
