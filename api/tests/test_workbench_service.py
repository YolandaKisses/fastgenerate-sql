from app.models.datasource import DataSource, DataSourceStatus
from app.models.setting import RuntimeSetting
from app.services import workbench_service
from app.services.workbench_service import (
    ask_llm_stream,
    normalize_note_name,
    note_used_payload,
    validate_sql_candidate,
)
from sqlmodel import SQLModel, Session, create_engine


def test_validate_sql_candidate_rejects_multi_statement_write_sql():
    result = validate_sql_candidate("SELECT * FROM users; DELETE FROM users")

    assert result["status"] == "invalid"
    assert "禁止执行多条语句" in result["reasons"]
    assert any("DELETE" in reason for reason in result["reasons"])


def test_normalize_note_name_accepts_markdown_paths():
    assert normalize_note_name("tables/user_profiles.md") == "user_profiles"


def test_note_used_payload_reports_hermes_note_without_sqlite_lookup():
    payload = note_used_payload("tables/user_profiles.md")

    assert payload == {"note": "user_profiles", "comment": ""}


def test_stream_omits_synthetic_generating_sql_status(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    knowledge_root = tmp_path / "vault"
    knowledge_dir = knowledge_root / "demo" / "tables"
    knowledge_dir.mkdir(parents=True)

    def fake_run_hermes_json(*args, **kwargs):
        return {
            "type": "sql_candidate",
            "sql": "SELECT 1",
            "explanation": "测试 SQL",
            "used_notes": [],
        }

    monkeypatch.setattr(workbench_service, "run_hermes_json", fake_run_hermes_json)
    monkeypatch.setattr(
        workbench_service,
        "retrieve_relevant_schema",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Workbench must not query sqlite schema")),
    )

    with Session(engine) as session:
        ds = DataSource(
            name="demo",
            db_type="mysql",
            host="localhost",
            port=3306,
            database="demo",
            username="root",
            password="secret",
            status=DataSourceStatus.READY,
        )
        session.add(ds)
        session.add(RuntimeSetting(key="obsidian_vault_root", value=str(knowledge_root)))
        session.commit()
        session.refresh(ds)

        stream = "".join(ask_llm_stream(session, ds.id, "查一下测试数据"))

    assert "generating_sql" not in stream
    assert "Hermes 正在生成 SQL" not in stream


def test_stream_labels_hermes_used_notes_as_references_not_hits(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    knowledge_root = tmp_path / "vault"
    knowledge_dir = knowledge_root / "demo" / "tables"
    knowledge_dir.mkdir(parents=True)

    def fake_run_hermes_json(*args, **kwargs):
        return {
            "type": "sql_candidate",
            "sql": "SELECT 1",
            "explanation": "测试 SQL",
            "used_notes": ["demo_users"],
        }

    monkeypatch.setattr(workbench_service, "run_hermes_json", fake_run_hermes_json)

    with Session(engine) as session:
        ds = DataSource(
            name="demo",
            db_type="mysql",
            host="localhost",
            port=3306,
            database="demo",
            username="root",
            password="secret",
            status=DataSourceStatus.READY,
        )
        session.add(ds)
        session.add(RuntimeSetting(key="obsidian_vault_root", value=str(knowledge_root)))
        session.commit()
        session.refresh(ds)

        stream = "".join(ask_llm_stream(session, ds.id, "1"))

    assert "event: note_used" in stream
    assert "demo_users" in stream


def test_clarification_choice_skips_local_ambiguity_and_reaches_hermes(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    knowledge_root = tmp_path / "vault"
    knowledge_dir = knowledge_root / "demo" / "tables"
    knowledge_dir.mkdir(parents=True)

    called = False

    def fake_run_hermes_json(*args, **kwargs):
        nonlocal called
        called = True
        return {
            "type": "sql_candidate",
            "sql": "SELECT * FROM demo_accounts",
            "explanation": "按 A 选项生成 SQL",
            "used_notes": ["demo_accounts"],
        }

    monkeypatch.setattr(workbench_service, "run_hermes_json", fake_run_hermes_json)
    monkeypatch.setattr(
        workbench_service,
        "retrieve_relevant_schema",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Workbench must not query sqlite schema")),
    )

    with Session(engine) as session:
        ds = DataSource(
            name="demo",
            db_type="mysql",
            host="localhost",
            port=3306,
            database="demo",
            username="root",
            password="secret",
            status=DataSourceStatus.READY,
        )
        session.add(ds)
        session.commit()
        session.refresh(ds)
        session.add(RuntimeSetting(key="obsidian_vault_root", value=str(knowledge_root)))
        session.commit()

        history = [
            {"role": "user", "content": "1"},
            {"role": "assistant", "content": "请选择：\nA) 账户表\nB) 活动表"},
        ]
        stream = "".join(ask_llm_stream(session, ds.id, "A", history))

    assert called is True
    assert "需要澄清" not in stream
    assert "正在检索知识库" not in stream
    assert "event: note_hit" not in stream
    assert "SELECT * FROM demo_accounts" in stream
