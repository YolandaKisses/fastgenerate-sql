from sqlmodel import SQLModel, Session, create_engine, select

from app.models.datasource import DataSource, DataSourceStatus, SyncStatus
from app.models.routine import RoutineDefinition, RoutineSqlFact
from app.services import routine_service
from app.services.routine_lineage_service import (
    extract_sql_statements,
    parse_statement_tables,
)


class FakeOracleResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeOracleConnection:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, _statement):
        return FakeOracleResult(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeOracleEngine:
    def __init__(self, rows):
        self._rows = rows

    def connect(self):
        return FakeOracleConnection(self._rows)

    def dispose(self):
        return None


def test_sync_routines_for_oracle_persists_full_text_and_removes_obsolete_entries(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    oracle_rows = [
        ("APP", "P_SYNC_USERS", "PROCEDURE", 1, "PROCEDURE P_SYNC_USERS IS"),
        ("APP", "P_SYNC_USERS", "PROCEDURE", 2, "BEGIN"),
        ("APP", "P_SYNC_USERS", "PROCEDURE", 3, "  NULL;"),
        ("APP", "P_SYNC_USERS", "PROCEDURE", 4, "END;"),
        ("APP", "F_USER_COUNT", "FUNCTION", 1, "FUNCTION F_USER_COUNT RETURN NUMBER IS"),
        ("APP", "F_USER_COUNT", "FUNCTION", 2, "BEGIN"),
        ("APP", "F_USER_COUNT", "FUNCTION", 3, "  RETURN 1;"),
        ("APP", "F_USER_COUNT", "FUNCTION", 4, "END;"),
    ]

    monkeypatch.setattr(
        routine_service.sqlalchemy,
        "create_engine",
        lambda *args, **kwargs: FakeOracleEngine(oracle_rows),
    )

    with Session(engine) as session:
        ds = DataSource(
            name="oracle-demo",
            db_type="oracle",
            host="localhost",
            port=1521,
            database="orclpdb",
            username="system",
            password="secret",
            user_id="u1",
            status=DataSourceStatus.CONNECTION_OK,
            sync_status=SyncStatus.NEVER_SYNCED,
        )
        session.add(ds)
        session.commit()
        session.refresh(ds)

        session.add(
            RoutineDefinition(
                datasource_id=ds.id,
                owner="APP",
                name="OLD_PROC",
                routine_type="PROCEDURE",
                definition_text="obsolete",
            )
        )
        session.commit()

        result = routine_service.sync_routines_for_datasource(session, ds)

        assert result["success"] is True
        assert result["count"] == 2

        routines = session.exec(
            select(RoutineDefinition).where(RoutineDefinition.datasource_id == ds.id)
        ).all()
        routines_by_key = {(item.owner, item.name, item.routine_type): item for item in routines}

        assert set(routines_by_key) == {
            ("APP", "P_SYNC_USERS", "PROCEDURE"),
            ("APP", "F_USER_COUNT", "FUNCTION"),
        }
        assert routines_by_key[("APP", "P_SYNC_USERS", "PROCEDURE")].definition_text == (
            "PROCEDURE P_SYNC_USERS IS\nBEGIN\n  NULL;\nEND;"
        )
        assert routines_by_key[("APP", "F_USER_COUNT", "FUNCTION")].definition_text == (
            "FUNCTION F_USER_COUNT RETURN NUMBER IS\nBEGIN\n  RETURN 1;\nEND;"
        )


def test_sync_routines_for_datasource_rejects_non_oracle_datasource():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        ds = DataSource(
            name="mysql-demo",
            db_type="mysql",
            host="localhost",
            port=3306,
            database="demo",
            username="root",
            password="secret",
            user_id="u1",
        )
        session.add(ds)
        session.commit()
        session.refresh(ds)

        result = routine_service.sync_routines_for_datasource(session, ds)

        assert result["success"] is False
        assert result["message"] == "当前仅支持 Oracle 存储过程/函数同步"


def test_sync_routines_for_oracle_builds_statement_level_table_facts(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    oracle_rows = [
        ("APP", "P_SYNC_USERS", "PROCEDURE", 1, "PROCEDURE P_SYNC_USERS IS"),
        ("APP", "P_SYNC_USERS", "PROCEDURE", 2, "BEGIN"),
        ("APP", "P_SYNC_USERS", "PROCEDURE", 3, "  INSERT INTO user_snapshot"),
        ("APP", "P_SYNC_USERS", "PROCEDURE", 4, "  SELECT * FROM users u JOIN orders o ON o.user_id = u.id;"),
        ("APP", "P_SYNC_USERS", "PROCEDURE", 5, "END;"),
    ]

    monkeypatch.setattr(
        routine_service.sqlalchemy,
        "create_engine",
        lambda *args, **kwargs: FakeOracleEngine(oracle_rows),
    )

    with Session(engine) as session:
        ds = DataSource(
            name="oracle-demo",
            db_type="oracle",
            host="localhost",
            port=1521,
            database="orclpdb",
            username="system",
            password="secret",
            user_id="u1",
            status=DataSourceStatus.CONNECTION_OK,
            sync_status=SyncStatus.NEVER_SYNCED,
        )
        session.add(ds)
        session.commit()
        session.refresh(ds)

        result = routine_service.sync_routines_for_datasource(session, ds)

        assert result["success"] is True

        facts = session.exec(
            select(RoutineSqlFact)
            .where(RoutineSqlFact.datasource_id == ds.id)
            .order_by(RoutineSqlFact.usage_type, RoutineSqlFact.table_name)
        ).all()

        assert [(item.usage_type, item.table_name) for item in facts] == [
            ("read", "orders"),
            ("read", "users"),
            ("write", "user_snapshot"),
        ]
        assert all(item.parser_name for item in facts)


def test_extract_sql_statements_keeps_semicolons_inside_string_literals():
    definition_text = """
    PROCEDURE P_DEMO IS
    BEGIN
      insert into temp_mdm_source_procedurce
      select dd.object_name
      from temp_mdm_dba_source t
      where regexp_substr(t.text, dd.procedure_name || ';') is not null;
    END;
    """

    statements = extract_sql_statements(definition_text)

    assert len(statements) == 1
    assert "dd.procedure_name || ';'" in statements[0][0]


def test_sync_routines_for_oracle_extracts_truncate_as_write_fact(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    oracle_rows = [
        ("APP", "P_TRUNCATE_CACHE", "PROCEDURE", 1, "PROCEDURE P_TRUNCATE_CACHE IS"),
        ("APP", "P_TRUNCATE_CACHE", "PROCEDURE", 2, "BEGIN"),
        ("APP", "P_TRUNCATE_CACHE", "PROCEDURE", 3, "  EXECUTE IMMEDIATE 'TRUNCATE TABLE temp_cache';"),
        ("APP", "P_TRUNCATE_CACHE", "PROCEDURE", 4, "END;"),
    ]

    monkeypatch.setattr(
        routine_service.sqlalchemy,
        "create_engine",
        lambda *args, **kwargs: FakeOracleEngine(oracle_rows),
    )

    with Session(engine) as session:
        ds = DataSource(
            name="oracle-demo",
            db_type="oracle",
            host="localhost",
            port=1521,
            database="orclpdb",
            username="system",
            password="secret",
            user_id="u1",
            status=DataSourceStatus.CONNECTION_OK,
            sync_status=SyncStatus.NEVER_SYNCED,
        )
        session.add(ds)
        session.commit()
        session.refresh(ds)

        result = routine_service.sync_routines_for_datasource(session, ds)

        assert result["success"] is True
        facts = session.exec(
            select(RoutineSqlFact).where(RoutineSqlFact.datasource_id == ds.id)
        ).all()

        assert [(item.usage_type, item.table_name) for item in facts] == [
            ("write", "temp_cache"),
        ]


def test_parse_statement_tables_cleans_insert_target_alias_for_sqllineage():
    statement = """
    INSERT INTO MDM_PROC_TABLE t
    (F_PROC_ID, F_TABLE_ID, VC_ISAUTO, D_UPDATETIME)
    select f_proc_id, f_table_id, '1', sysdate
    from temp_MDM_proc_table s
    where not exists (select 1
    from mdm_proc_table zz
    where zz.f_proc_id = s.f_proc_id
    and zz.f_table_id = s.f_table_id)
    """

    reads, writes, parser_name = parse_statement_tables(statement)

    assert parser_name == "sqllineage"
    assert "temp_mdm_proc_table" in {name.lower() for name in reads}
    assert "mdm_proc_table" in {name.lower() for name in writes}
