from app.models.datasource import DataSource, DataSourceStatus, SyncStatus
from app.models.setting import RuntimeSetting
from app.services import workbench_service
from app.api.routes.workbench import is_valid_hermes_session_id
from app.services.hermes_service import parse_hermes_session_id, run_hermes_session_json
from app.services.workbench_service import (
    ask_llm_stream,
    can_ask_datasource,
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


def test_parse_hermes_session_id_ignores_status_text():
    output = """
session: started
{"type":"sql_candidate","sql":"SELECT 1"}
session_id: hermes-session-1
"""

    assert parse_hermes_session_id(output) == "hermes-session-1"
    assert parse_hermes_session_id("session: complete") is None


def test_run_hermes_session_json_falls_back_to_new_session_from_list(monkeypatch):
    calls = []

    class FakeCompletedProcess:
        def __init__(self, stdout: str):
            self.stdout = stdout
            self.stderr = ""

    def fake_run(command, **kwargs):
        calls.append(command)
        if command[1:3] == ["sessions", "list"] and len(calls) == 1:
            return FakeCompletedProcess(
                "Title Preview Last Active ID\n"
                "old preview 1m ago 20260430_100000_old111\n"
            )
        if command[1:2] == ["chat"]:
            return FakeCompletedProcess('{"type":"clarification","message":"请选择","used_notes":[]}')
        if command[1:3] == ["sessions", "list"]:
            return FakeCompletedProcess(
                "Title Preview Last Active ID\n"
                "new preview now 20260430_195311_e42ded\n"
                "old preview 1m ago 20260430_100000_old111\n"
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("app.services.hermes_service.subprocess.run", fake_run)

    result, session_id = run_hermes_session_json(
        "prompt",
        hermes_cli_path="/bin/hermes",
    )

    assert result["type"] == "clarification"
    assert session_id == "20260430_195311_e42ded"
    chat_command = next(command for command in calls if command[1:2] == ["chat"])
    assert "-t" in chat_command
    assert chat_command[chat_command.index("-t") + 1] == "file"


def test_hermes_session_id_route_validation_rejects_unsafe_values():
    assert is_valid_hermes_session_id("hermes-session_1.2:3")
    assert not is_valid_hermes_session_id("")
    assert not is_valid_hermes_session_id("session id with spaces")
    assert not is_valid_hermes_session_id("../session")
    assert not is_valid_hermes_session_id("a" * 129)


def test_can_ask_datasource_requires_connection_ok_and_sync_success():
    assert can_ask_datasource(
        DataSource(
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
    )


def test_schema_sync_success_alone_does_not_allow_asking():
    assert not can_ask_datasource(
        DataSource(
            name="demo",
            db_type="mysql",
            host="localhost",
            port=3306,
            database="demo",
            username="root",
            password="secret",
            status=DataSourceStatus.CONNECTION_OK,
            sync_status=SyncStatus.NEVER_SYNCED,
            last_sync_message="Schema 已同步，请同步到知识库",
        )
    )
    assert not can_ask_datasource(
        DataSource(
            name="demo",
            db_type="mysql",
            host="localhost",
            port=3306,
            database="demo",
            username="root",
            password="secret",
            status=DataSourceStatus.READY,
            sync_status=SyncStatus.SYNC_SUCCESS,
        )
    )
    assert not can_ask_datasource(
        DataSource(
            name="demo",
            db_type="mysql",
            host="localhost",
            port=3306,
            database="demo",
            username="root",
            password="secret",
            status=DataSourceStatus.CONNECTION_OK,
            sync_status=SyncStatus.NEVER_SYNCED,
        )
    )


def test_stream_omits_synthetic_generating_sql_status(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    knowledge_root = tmp_path / "vault"
    knowledge_dir = knowledge_root / "demo" / "tables"
    knowledge_dir.mkdir(parents=True)

    def fake_run_hermes_session_json(*args, **kwargs):
        return (
            {
                "type": "sql_candidate",
                "sql": "SELECT 1",
                "explanation": "测试 SQL",
                "used_notes": [],
            },
            "hermes-session-1",
        )

    monkeypatch.setattr(workbench_service, "run_hermes_session_json", fake_run_hermes_session_json)
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
            status=DataSourceStatus.CONNECTION_OK,
            sync_status=SyncStatus.SYNC_SUCCESS,
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

    def fake_run_hermes_session_json(*args, **kwargs):
        return (
            {
                "type": "sql_candidate",
                "sql": "SELECT 1",
                "explanation": "测试 SQL",
                "used_notes": ["demo_users"],
            },
            "hermes-session-1",
        )

    monkeypatch.setattr(workbench_service, "run_hermes_session_json", fake_run_hermes_session_json)

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

    def fake_run_hermes_session_json(prompt, *args, **kwargs):
        nonlocal called
        called = True
        assert "### 对话历史" not in prompt
        assert kwargs.get("session_id") == "hermes-session-1"
        return (
            {
                "type": "sql_candidate",
                "sql": "SELECT * FROM demo_accounts",
                "explanation": "按 A 选项生成 SQL",
                "used_notes": ["demo_accounts"],
            },
            "hermes-session-1",
        )

    monkeypatch.setattr(workbench_service, "run_hermes_session_json", fake_run_hermes_session_json)
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
            status=DataSourceStatus.CONNECTION_OK,
            sync_status=SyncStatus.SYNC_SUCCESS,
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
        stream = "".join(ask_llm_stream(session, ds.id, "A", history, "hermes-session-1"))

    assert called is True
    assert "需要澄清" not in stream
    assert "正在检索知识库" not in stream
    assert "event: note_hit" not in stream
    assert "SELECT * FROM demo_accounts" in stream
    assert "hermes-session-1" in stream
