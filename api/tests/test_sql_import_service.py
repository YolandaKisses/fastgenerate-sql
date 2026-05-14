from sqlmodel import Session, SQLModel, create_engine

from app.models.datasource import DataSource
from app.services.sql_import_service import extract_sql_statements, parse_sql_text


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
