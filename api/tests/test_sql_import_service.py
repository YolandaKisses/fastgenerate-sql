import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.datasource import DataSource
from app.models.routine import RoutineDefinition
from app.models.schema import SchemaField, SchemaTable
from app.models.sql_import import SqlImportBatch, SqlImportBatchStatus, SqlImportFile
from app.models.view import ViewDefinition
from app.services import sql_import_service
from app.services.sql_import_service import ParsedSqlImport, extract_sql_statements, parse_sql_text


def test_extract_sql_statements_ignores_oracle_export_headers_and_prompt_lines():
    content = """
    ---------------------------------------------------------
    -- Export file for user DD_DM@10.6.14.43:1521/DATASRV --
    ---------------------------------------------------------

    set define off
    spool metadata.log

    prompt
    prompt Creating table ACC_IVSM_ACC
    prompt ===========================
    prompt
    create table ACC_IVSM_ACC
    (
      ivsm_acc_num VARCHAR2(32) default ' ' not null
    )
    ;
    """

    statements = extract_sql_statements(content)

    assert len(statements) == 1
    assert statements[0].lower().startswith("create table acc_ivsm_acc")


def test_parse_sql_text_reads_objects_from_oracle_export_format():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    content = """
    prompt
    prompt Creating function FUN_TRADEDAY
    prompt ==============================
    prompt
    create or replace function fun_tradeday(i_date in date) return date IS
    begin
      return i_date;
    end fun_tradeday;
    /

    prompt
    prompt Creating table ACC_IVSM_ACC
    prompt ===========================
    prompt
    create table ACC_IVSM_ACC
    (
      ivsm_acc_num VARCHAR2(32) default ' ' not null
    )
    ;
    """

    with Session(engine) as session:
      datasource = DataSource(
          name="dd_dm",
          db_type="oracle",
          source_mode="sql_file",
          user_id="u1",
          host="",
          port=0,
          database="DD_DM",
          username="",
          password="",
      )
      parsed = parse_sql_text(content, datasource)

    assert len(parsed.tables) == 1
    assert parsed.tables[0].name == "ACC_IVSM_ACC"
    assert len(parsed.routines) == 1
    assert parsed.routines[0].name == "fun_tradeday"


def test_parse_sql_text_reads_force_view_from_oracle_export_format():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    content = """
    prompt
    prompt Creating view V_DIM_OBJ_SECURITY_TYPE_DETAIL
    prompt ============================================
    prompt
    CREATE OR REPLACE FORCE VIEW V_DIM_OBJ_SECURITY_TYPE_DETAIL AS
    SELECT 1 AS SECURITY_INNER_CD
      FROM DUAL;
    """

    with Session(engine) as session:
        datasource = DataSource(
            name="dd_dm",
            db_type="oracle",
            source_mode="sql_file",
            user_id="u1",
            host="",
            port=0,
            database="DD_DM",
            username="",
            password="",
        )
        parsed = parse_sql_text(content, datasource)

    assert len(parsed.views) == 1
    assert parsed.views[0].name == "V_DIM_OBJ_SECURITY_TYPE_DETAIL"


def test_parse_latest_sql_import_batch_marks_batch_processing_before_parse(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        datasource = DataSource(
            name="dd_dm",
            db_type="oracle",
            source_mode="sql_file",
            user_id="u1",
            host="",
            port=0,
            database="DD_DM",
            username="",
            password="",
        )
        session.add(datasource)
        session.commit()
        session.refresh(datasource)

        batch = SqlImportBatch(datasource_id=datasource.id, batch_no=1)
        session.add(batch)
        session.commit()
        session.refresh(batch)

        session.add(
            SqlImportFile(
                batch_id=batch.id,
                file_name="demo.sql",
                file_content="create table demo(id number);",
                sort_order=0,
            )
        )
        session.commit()

        def fake_parse_sql_text(content: str, ds: DataSource) -> ParsedSqlImport:
            with Session(engine) as check_session:
                stored_batch = check_session.get(SqlImportBatch, batch.id)
                assert stored_batch is not None
                assert stored_batch.status == SqlImportBatchStatus.PROCESSING
            return ParsedSqlImport()

        monkeypatch.setattr(sql_import_service, "parse_sql_text", fake_parse_sql_text)

        result = sql_import_service.parse_latest_sql_import_batch(session, datasource)

    assert result["success"] is True


def test_parse_latest_sql_import_batch_marks_batch_failed_on_error(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        datasource = DataSource(
            name="dd_dm",
            db_type="oracle",
            source_mode="sql_file",
            user_id="u1",
            host="",
            port=0,
            database="DD_DM",
            username="",
            password="",
        )
        session.add(datasource)
        session.commit()
        session.refresh(datasource)

        batch = SqlImportBatch(datasource_id=datasource.id, batch_no=1)
        session.add(batch)
        session.commit()
        session.refresh(batch)

        session.add(
            SqlImportFile(
                batch_id=batch.id,
                file_name="demo.sql",
                file_content="create table demo(id number);",
                sort_order=0,
            )
        )
        session.commit()

        def fake_parse_sql_text(content: str, ds: DataSource) -> ParsedSqlImport:
            raise ValueError("boom")

        monkeypatch.setattr(sql_import_service, "parse_sql_text", fake_parse_sql_text)

        with pytest.raises(HTTPException) as exc_info:
            sql_import_service.parse_latest_sql_import_batch(session, datasource)

        assert exc_info.value.status_code == 400

        stored_batch = session.exec(select(SqlImportBatch)).one()
        session.refresh(datasource)

    assert stored_batch.status == SqlImportBatchStatus.FAILED
    assert stored_batch.message == "boom"
    assert datasource.source_status == "parse_failed"
    assert datasource.source_message == "boom"


def test_parse_latest_sql_import_batch_rolls_back_metadata_cleanup_on_failure(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        datasource = DataSource(
            name="dd_dm",
            db_type="oracle",
            source_mode="sql_file",
            user_id="u1",
            host="",
            port=0,
            database="DD_DM",
            username="",
            password="",
        )
        session.add(datasource)
        session.commit()
        session.refresh(datasource)

        table = SchemaTable(
            datasource_id=datasource.id,
            name="OLD_TABLE",
            original_comment="keep me",
        )
        session.add(table)
        session.commit()
        session.refresh(table)
        session.add(
            SchemaField(
                table_id=table.id,
                name="old_field",
                type="VARCHAR2(32)",
                original_comment="old field",
            )
        )
        session.add(
            ViewDefinition(
                datasource_id=datasource.id,
                owner="DD_DM",
                name="OLD_VIEW",
                definition_text="select 1 from dual",
            )
        )
        session.add(
            RoutineDefinition(
                datasource_id=datasource.id,
                owner="DD_DM",
                name="OLD_ROUTINE",
                routine_type="FUNCTION",
                definition_text="return 1;",
            )
        )
        session.commit()

        batch = SqlImportBatch(datasource_id=datasource.id, batch_no=1)
        session.add(batch)
        session.commit()
        session.refresh(batch)

        session.add(
            SqlImportFile(
                batch_id=batch.id,
                file_name="demo.sql",
                file_content="create table NEW_TABLE(id number);",
                sort_order=0,
            )
        )
        session.commit()

        def fake_rebuild_view_sql_facts(*args, **kwargs):
            raise ValueError("lineage rebuild failed")

        monkeypatch.setattr(
            sql_import_service,
            "rebuild_view_sql_facts",
            fake_rebuild_view_sql_facts,
        )

        with pytest.raises(HTTPException) as exc_info:
            sql_import_service.parse_latest_sql_import_batch(session, datasource)

        assert exc_info.value.status_code == 400

        tables = session.exec(
            select(SchemaTable).where(SchemaTable.datasource_id == datasource.id)
        ).all()
        fields = session.exec(
            select(SchemaField).where(SchemaField.table_id == table.id)
        ).all()
        views = session.exec(
            select(ViewDefinition).where(ViewDefinition.datasource_id == datasource.id)
        ).all()
        routines = session.exec(
            select(RoutineDefinition).where(RoutineDefinition.datasource_id == datasource.id)
        ).all()

    assert [item.name for item in tables] == ["OLD_TABLE"]
    assert [item.name for item in fields] == ["old_field"]
    assert [item.name for item in views] == ["OLD_VIEW"]
    assert [item.name for item in routines] == ["OLD_ROUTINE"]
