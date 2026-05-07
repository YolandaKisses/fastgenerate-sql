from app.models.datasource import DataSource, DataSourceStatus, SyncStatus
from app.models.schema import SchemaField, SchemaTable
from app.models.setting import RuntimeSetting
from app.services import workbench_service
from app.api.routes.workbench import is_valid_hermes_session_id
from app.services.hermes_service import hermes_trace_message_from_line, iter_hermes_session_json, parse_hermes_json_output, parse_hermes_session_id, run_hermes_session_json
from app.services.workbench_service import (
    _parse_frontmatter,
    ask_llm,
    ask_llm_stream,
    can_ask_datasource,
    build_schema_retrieval_question,
    normalize_note_name,
    note_used_payload,
    read_relevant_table_notes,
    retrieve_relevant_business_rules,
    retrieve_relevant_schema,
    should_allow_schema_fallback,
    validate_sql_against_schema,
    validate_sql_candidate,
)
from sqlmodel import SQLModel, Session, create_engine


def test_validate_sql_candidate_rejects_multi_statement_write_sql():
    result = validate_sql_candidate("SELECT * FROM users; DELETE FROM users")

    assert result["status"] == "invalid"
    assert any("禁止执行多条语句" in reason for reason in result["reasons"])


def test_normalize_note_name_accepts_markdown_paths():
    assert normalize_note_name("tables/user_profiles.md") == "user_profiles"


def test_note_used_payload_reports_hermes_note_without_sqlite_lookup():
    payload = note_used_payload("tables/user_profiles.md")

    assert payload == {"note": "user_profiles", "comment": ""}


def test_read_relevant_table_notes_truncates_on_line_boundary(tmp_path):
    table = SchemaTable(id=1, datasource_id=1, name="large_table")
    note_path = tmp_path / "large_table.md"
    note_path.write_text("first line\n" + ("x" * 4100) + "\nthird line", encoding="utf-8")

    text, used_notes = read_relevant_table_notes(
        [{"table": table, "fields": []}],
        tmp_path,
    )

    assert used_notes == ["large_table"]
    assert text.endswith("\n（后续内容已裁剪）")
    assert "third line" not in text


def test_parse_frontmatter_supports_scalar_inline_list_and_quoted_values():
    meta, body = _parse_frontmatter(
        """---
tables: orders
keywords: ["用户", '订单:统计']
summary: "订单: 聚合规则"
---
正文内容
""",
    )

    assert meta == {
        "tables": "orders",
        "keywords": ["用户", "订单:统计"],
        "summary": "订单: 聚合规则",
    }
    assert body == "正文内容"


def test_retrieve_relevant_business_rules_does_not_match_unrelated_index_refs(tmp_path):
    rules_dir = tmp_path / "business_rules"
    rules_dir.mkdir()
    (rules_dir / "_index.md").write_text(
        "\n".join([
            "- [[orders_join_rule]] 订单与用户关联",
            "- [[revenue_caliber]] 营收口径",
        ]),
        encoding="utf-8",
    )
    (rules_dir / "orders_join_rule.md").write_text(
        """---
tables: [orders, users]
keywords: [下单, 用户]
summary: 订单与用户关联
---
orders.user_id = users.id
""",
        encoding="utf-8",
    )
    (rules_dir / "revenue_caliber.md").write_text(
        """---
tables: revenue
keywords: [营收]
summary: 营收口径
---
排除退款单
""",
        encoding="utf-8",
    )

    context, used_rules = retrieve_relevant_business_rules(
        "查询天气趋势",
        ["weather_forecast"],
        rules_dir,
    )

    assert context == ""
    assert used_rules == []


def test_retrieve_relevant_business_rules_uses_index_to_boost_related_rules(tmp_path):
    rules_dir = tmp_path / "business_rules"
    rules_dir.mkdir()
    (rules_dir / "_index.md").write_text(
        "- [[orders_join_rule]] 订单与用户关联\n",
        encoding="utf-8",
    )
    (rules_dir / "orders_join_rule.md").write_text(
        """---
tables: orders
summary: 订单关联规则
---
orders.user_id = users.id
""",
        encoding="utf-8",
    )

    context, used_rules = retrieve_relevant_business_rules(
        "查询订单数据",
        ["orders"],
        rules_dir,
    )

    assert "### Rule Index" in context
    assert "### Rule: orders_join_rule" in context
    assert used_rules == ["_index", "orders_join_rule"]


def test_schema_retrieval_question_uses_recent_user_history_only():
    history = [
        {"role": "user", "content": f"用户问题 {idx}"}
        for idx in range(1, 8)
    ]
    history.insert(3, {"role": "assistant", "content": "请选择：A) ..."})

    retrieval_question = build_schema_retrieval_question("A", history)

    assert "用户问题 1" not in retrieval_question
    assert "用户问题 4" in retrieval_question
    assert "用户问题 7" in retrieval_question
    assert retrieval_question.endswith("A")


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


def test_iter_hermes_session_json_emits_trace_events_before_result(monkeypatch):
    class FakeStdout:
        def __iter__(self):
            return iter([
                "Hermes is reading notes\n",
                '{"type":"clarification","message":"请选择","used_notes":[]}\n',
                "session_id: 20260502_111111_stream\n",
            ])

        def close(self):
            pass

    class FakeProcess:
        stdout = FakeStdout()

        def wait(self, timeout=None):
            return 0

    popen_calls = []

    def fake_popen(command, **kwargs):
        popen_calls.append(command)
        return FakeProcess()

    monkeypatch.setattr("app.services.hermes_service.subprocess.Popen", fake_popen)

    events = list(iter_hermes_session_json("prompt", hermes_cli_path="/bin/hermes", session_id="previous-session"))

    assert events[0] == {"type": "trace", "message": "Hermes is reading notes"}
    assert events[-1]["type"] == "result"
    assert events[-1]["result"]["type"] == "clarification"
    assert events[-1]["session_id"] == "20260502_111111_stream"
    chat_command = popen_calls[0]
    assert "-Q" not in chat_command
    assert "-v" in chat_command


def test_parse_hermes_json_output_uses_final_result_from_verbose_output():
    output = """
返回格式示例：
{"type": "clarification", "message": "问题存在歧义", "used_notes": ["示例笔记"]}
Initializing agent...
run_agent - INFO - Verbose logging enabled
{"type": "clarification", "message": "请澄清：A) 基本信息 B) 登录日志", "used_notes": ["demo_users"]}
session_id: 20260502_113543_abcd
"""

    result = parse_hermes_json_output(output)

    assert result == {
        "type": "clarification",
        "message": "请澄清：A) 基本信息 B) 登录日志",
        "used_notes": ["demo_users"],
    }


def test_parse_hermes_json_output_does_not_use_prompt_example_sql():
    output = """
返回 JSON 格式，只允许以下两种：
{"type": "clarification", "message": "问题存在歧义，请选择最符合您需求的选项：\nA) ...\nB) ...", "used_notes": ["已读取的笔记文件名"]}
{"type": "sql_candidate", "sql": "SELECT ...", "explanation": "SQL 含义说明", "used_notes": ["已读取的笔记文件名"]}
这是一个完全无法与 SQL 生成关联的问题。根据规则，我需要进入澄清模式，给出候选选项。
Conversation completed after 3 OpenAI-compatible API call(s)
"""

    result = parse_hermes_json_output(output)

    assert result["type"] == "clarification"
    assert "SELECT ..." not in result.get("sql", "")
    assert "不在当前数据库查询范围" in result["message"]


def test_hermes_trace_message_filters_noisy_verbose_lines():
    assert hermes_trace_message_from_line("Initializing agent...") is None
    assert hermes_trace_message_from_line("11:35:43 - run_agent - INFO - Verbose logging enabled") is None
    assert hermes_trace_message_from_line("### 用户当前问题：今天吃啥") is None
    assert hermes_trace_message_from_line("Hermes is reading demo_users.md") == "Hermes is reading demo_users.md"


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
            status=DataSourceStatus.CONNECTION_OK,
            sync_status=SyncStatus.NEVER_SYNCED,
        )
    )


def test_ask_llm_builds_sqlite_first_prompt_with_relevant_notes_only(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    knowledge_root = tmp_path / "vault"
    knowledge_dir = knowledge_root / "demo" / "tables"
    knowledge_dir.mkdir(parents=True)
    (knowledge_dir / "user_register_log.md").write_text("register_time 表示完成注册时间", encoding="utf-8")
    (knowledge_dir / "weather_forecast.md").write_text("unrelated weather data", encoding="utf-8")

    captured = {}

    def fake_run_hermes_session_json(prompt, *args, **kwargs):
        captured["prompt"] = prompt
        return (
            {
                "type": "sql_candidate",
                "sql": "SELECT COUNT(*) FROM user_register_log",
                "explanation": "统计注册记录",
                "used_notes": ["user_register_log"],
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

        table = SchemaTable(datasource_id=ds.id, name="user_register_log", original_comment="用户注册日志")
        unrelated = SchemaTable(datasource_id=ds.id, name="weather_forecast", original_comment="weather data")
        session.add(table)
        session.add(unrelated)
        session.commit()
        session.refresh(table)
        session.refresh(unrelated)
        session.add(SchemaField(table_id=table.id, name="register_time", type="DATETIME", original_comment="注册时间"))
        session.add(SchemaField(table_id=table.id, name="user_id", type="BIGINT", original_comment="用户ID"))
        session.add(SchemaField(table_id=unrelated.id, name="temperature", type="FLOAT", original_comment="celsius"))
        session.commit()

        result = ask_llm(session, ds.id, "统计注册用户")

    assert result["type"] == "sql_candidate"
    assert "Schema Context" in captured["prompt"]
    assert "表: user_register_log" in captured["prompt"]
    assert "register_time (DATETIME)" in captured["prompt"]
    assert "Obsidian Notes" in captured["prompt"]
    assert "register_time 表示完成注册时间" in captured["prompt"]
    assert "unrelated weather data" not in captured["prompt"]
    assert "唯一可信的表字段来源" in captured["prompt"]
    assert "主要知识来源是 Obsidian" not in captured["prompt"]


def test_ask_llm_retries_clarification_that_claims_present_schema_is_missing(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    knowledge_root = tmp_path / "vault"
    knowledge_dir = knowledge_root / "demo" / "tables"
    knowledge_dir.mkdir(parents=True)
    (knowledge_dir / "demo_users.md").write_text("company 对应工作单位", encoding="utf-8")

    prompts: list[str] = []
    calls = {"count": 0}

    def fake_run_hermes_session_json(prompt, *args, **kwargs):
        prompts.append(prompt)
        calls["count"] += 1
        if calls["count"] == 1:
            return (
                {
                    "type": "clarification",
                    "message": "A) 最近登陆日期取 demo_users 表的 last_login_at；消费记录无法从当前可用表中获取，需补充 user_orders 表 schema",
                    "used_notes": ["demo_users.md"],
                },
                "hermes-session-1",
            )
        return (
            {
                "type": "clarification",
                "message": "A) 仅查询张三在 user_orders 中的最近消费记录\nB) 仅查询张三的工作单位\nC) 取消本次查询",
                "used_notes": ["demo_users.md"],
            },
            "hermes-session-2",
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

        demo_users = SchemaTable(datasource_id=ds.id, name="demo_users", original_comment="示例用户表")
        user_orders = SchemaTable(
            datasource_id=ds.id,
            name="user_orders",
            original_comment="用户订单表",
            supplementary_comment="消费记录",
        )
        session.add(demo_users)
        session.add(user_orders)
        session.commit()
        session.refresh(demo_users)
        session.refresh(user_orders)
        session.add(SchemaField(table_id=demo_users.id, name="full_name", type="VARCHAR(128)", original_comment="姓名"))
        session.add(SchemaField(table_id=demo_users.id, name="company", type="VARCHAR(128)", original_comment="公司名称"))
        session.add(SchemaField(table_id=user_orders.id, name="order_amount", type="DECIMAL(12,2)", original_comment="消费金额"))
        session.commit()

        result = ask_llm(session, ds.id, "查询张三的工作单位和最近消费记录")

    assert calls["count"] == 2
    assert result["type"] == "clarification"
    assert "补充纠错要求" in prompts[1]
    assert "user_orders" in prompts[1]


def test_ask_llm_rejects_sql_with_unknown_schema_field(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    knowledge_root = tmp_path / "vault"
    knowledge_dir = knowledge_root / "demo" / "tables"
    knowledge_dir.mkdir(parents=True)
    (knowledge_dir / "user_register_log.md").write_text("用户注册日志", encoding="utf-8")

    def fake_run_hermes_session_json(*args, **kwargs):
        return (
                {
                    "type": "sql_candidate",
                    "sql": "SELECT user_register_log.missing_time FROM user_register_log",
                    "explanation": "错误字段",
                    "used_notes": ["user_register_log"],
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

        table = SchemaTable(datasource_id=ds.id, name="user_register_log", original_comment="用户注册日志")
        session.add(table)
        session.commit()
        session.refresh(table)
        session.add(SchemaField(table_id=table.id, name="register_time", type="DATETIME"))
        session.commit()

        result = ask_llm(session, ds.id, "统计注册用户")

    assert result["type"] == "error"
    assert "missing_time" in result["message"]
    assert "中不存在的字段" in result["message"]


def test_clarification_reply_uses_previous_user_question_for_schema_retrieval(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    knowledge_root = tmp_path / "vault"
    knowledge_dir = knowledge_root / "demo" / "tables"
    knowledge_dir.mkdir(parents=True)

    captured = {}

    def fake_run_hermes_session_json(prompt, *args, **kwargs):
        captured["prompt"] = prompt
        return (
            {
                "type": "sql_candidate",
                "sql": "SELECT COUNT(*) FROM user_register_log",
                "explanation": "按 A 选项统计注册用户",
                "used_notes": ["user_register_log"],
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

        table = SchemaTable(datasource_id=ds.id, name="user_register_log", original_comment="用户注册日志")
        unrelated = SchemaTable(datasource_id=ds.id, name="demo_accounts", original_comment="账户表")
        session.add(table)
        session.add(unrelated)
        session.commit()
        session.refresh(table)
        session.refresh(unrelated)
        session.add(SchemaField(table_id=table.id, name="user_id", type="BIGINT", original_comment="用户ID"))
        session.add(SchemaField(table_id=unrelated.id, name="id", type="BIGINT", original_comment="账户ID"))
        session.commit()

        result = ask_llm(
            session,
            ds.id,
            "A",
            history=[
                {"role": "user", "content": "统计注册用户"},
                {"role": "assistant", "content": "请选择：\nA) 按注册日志\nB) 按账户表"},
            ],
            hermes_session_id="hermes-session-1",
        )

    assert result["type"] == "sql_candidate"
    assert "表: user_register_log" in captured["prompt"]
    assert "user_id (BIGINT)" in captured["prompt"]


def test_unqualified_projection_alias_is_still_valid_without_schema_errors():
    table = SchemaTable(id=1, datasource_id=1, name="user_register_log")
    field = SchemaField(table_id=1, name="user_id", type="BIGINT")

    result = validate_sql_against_schema(
        "SELECT COUNT(*) AS total_users FROM user_register_log",
        [{"table": table, "fields": [field]}],
    )

    assert result["status"] == "valid"
    assert result["reasons"] == []
    assert result["warnings"] == []


def test_stream_omits_synthetic_generating_sql_status(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    knowledge_root = tmp_path / "vault"
    knowledge_dir = knowledge_root / "demo" / "tables"
    knowledge_dir.mkdir(parents=True)

    def fake_iter_hermes_session_json(*args, **kwargs):
        yield {
            "type": "result",
            "result": {
                "type": "sql_candidate",
                "sql": "SELECT 1",
                "explanation": "测试 SQL",
                "used_notes": [],
            },
            "session_id": "hermes-session-1",
        }

    monkeypatch.setattr(workbench_service, "iter_hermes_session_json", fake_iter_hermes_session_json)
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


def test_retrieve_relevant_schema_prefers_direct_business_synonyms_for_explicit_request():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

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

        demo_users = SchemaTable(datasource_id=ds.id, name="demo_users", original_comment="示例用户表")
        user_login_logs = SchemaTable(datasource_id=ds.id, name="user_login_logs", original_comment="用户登录日志表")
        user_orders = SchemaTable(datasource_id=ds.id, name="user_orders", original_comment="用户订单表")
        user_profiles = SchemaTable(datasource_id=ds.id, name="user_profiles", original_comment="用户资料表")
        session.add(demo_users)
        session.add(user_login_logs)
        session.add(user_orders)
        session.add(user_profiles)
        session.commit()
        session.refresh(demo_users)
        session.refresh(user_login_logs)
        session.refresh(user_orders)
        session.refresh(user_profiles)

        session.add(SchemaField(table_id=demo_users.id, name="full_name", type="VARCHAR(128)", original_comment="姓名"))
        session.add(SchemaField(table_id=demo_users.id, name="company", type="VARCHAR(128)", original_comment="公司名称", supplementary_comment="工作单位"))
        session.add(SchemaField(table_id=demo_users.id, name="job_title", type="VARCHAR(128)", original_comment="岗位名称"))
        session.add(SchemaField(table_id=user_login_logs.id, name="login_ip", type="VARCHAR(64)", original_comment="登录IP"))
        session.add(SchemaField(table_id=user_orders.id, name="order_amount", type="DECIMAL(12,2)", original_comment="订单金额"))
        session.add(SchemaField(table_id=user_profiles.id, name="address", type="VARCHAR(255)", original_comment="联系地址"))
        session.commit()

        candidates = retrieve_relevant_schema(session, ds.id, "查询李四的工作单位")

    assert [item["table"].name for item in candidates] == ["demo_users"]


def test_schema_fallback_is_disabled_for_clarification_option_with_history():
    assert not should_allow_schema_fallback(
        "A",
        history=[{"role": "user", "content": "查询张三的工作单位"}],
        hermes_session_id="session-1",
    )
    assert not should_allow_schema_fallback(
        "b",
        history=[{"role": "user", "content": "查询用户信息"}],
        hermes_session_id="session-1",
    )
    assert should_allow_schema_fallback(
        "查询用户信息",
        history=[{"role": "user", "content": "查询"}],
        hermes_session_id="session-1",
    )
    assert should_allow_schema_fallback("A", history=[], hermes_session_id=None)


def test_retrieve_relevant_schema_skips_fallback_for_clarification_option():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

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

        session.add(SchemaTable(datasource_id=ds.id, name="demo_users", original_comment="示例用户表"))
        session.add(SchemaTable(datasource_id=ds.id, name="user_orders", original_comment="用户订单表"))
        session.commit()

        candidates = retrieve_relevant_schema(
            session,
            ds.id,
            "查询张三的工作单位\nA",
            allow_fallback=False,
        )

    assert candidates == []


def test_stream_labels_hermes_used_notes_as_references_not_hits(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    knowledge_root = tmp_path / "vault"
    knowledge_dir = knowledge_root / "demo" / "tables"
    knowledge_dir.mkdir(parents=True)

    def fake_iter_hermes_session_json(*args, **kwargs):
        yield {
            "type": "result",
            "result": {
                "type": "sql_candidate",
                "sql": "SELECT 1",
                "explanation": "测试 SQL",
                "used_notes": ["demo_users"],
            },
            "session_id": "hermes-session-1",
        }

    monkeypatch.setattr(workbench_service, "iter_hermes_session_json", fake_iter_hermes_session_json)

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


def test_stream_forwards_hermes_trace_events(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    knowledge_root = tmp_path / "vault"
    knowledge_dir = knowledge_root / "demo" / "tables"
    knowledge_dir.mkdir(parents=True)

    def fake_iter_hermes_session_json(*args, **kwargs):
        yield {"type": "trace", "message": "Hermes is reading demo_users.md"}
        yield {
            "type": "result",
            "result": {
                "type": "sql_candidate",
                "sql": "SELECT 1",
                "explanation": "测试 SQL",
                "used_notes": ["demo_users"],
            },
            "session_id": "hermes-session-1",
        }

    monkeypatch.setattr(workbench_service, "iter_hermes_session_json", fake_iter_hermes_session_json)

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

    assert "event: hermes_trace" in stream
    assert "Hermes is reading demo_users.md" in stream
    assert "SELECT 1" in stream


def test_stream_converts_guessed_food_delivery_like_sql_to_clarification(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    knowledge_root = tmp_path / "vault"
    knowledge_dir = knowledge_root / "demo" / "tables"
    knowledge_dir.mkdir(parents=True)
    (knowledge_dir / "user_orders.md").write_text(
        "\n".join([
            "# user_orders",
            "| 字段名 | 类型 | 原始备注 |",
            "| --- | --- | --- |",
            "| product_name | VARCHAR(128) | 商品名称 |",
            "| created_at | DATETIME | 创建时间 |",
        ]),
        encoding="utf-8",
    )

    def fake_iter_hermes_session_json(*args, **kwargs):
        yield {
            "type": "result",
            "result": {
                "type": "sql_candidate",
                "sql": "SELECT * FROM user_orders WHERE DATE(created_at)=CURDATE() AND product_name LIKE '%外卖%'",
                "explanation": "用商品名称猜测餐饮/外卖订单",
                "used_notes": ["user_orders.md"],
            },
            "session_id": "hermes-session-1",
        }

    monkeypatch.setattr(workbench_service, "iter_hermes_session_json", fake_iter_hermes_session_json)

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

        stream = "".join(ask_llm_stream(session, ds.id, "A", None, "hermes-session-1"))

    assert '"type": "clarification"' in stream
    assert "是否允许用 product_name 关键词进行模糊匹配" in stream
    assert "sql_candidate" not in stream


def test_clarification_choice_keeps_sqlite_context_and_reaches_hermes(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    knowledge_root = tmp_path / "vault"
    knowledge_dir = knowledge_root / "demo" / "tables"
    knowledge_dir.mkdir(parents=True)

    called = False

    def fake_iter_hermes_session_json(prompt, *args, **kwargs):
        nonlocal called
        called = True
        assert "### 对话历史" not in prompt
        assert "Schema Context" in prompt
        assert "表: demo_accounts" in prompt
        assert kwargs.get("session_id") == "hermes-session-1"
        yield {
            "type": "result",
            "result": {
                "type": "sql_candidate",
                "sql": "SELECT * FROM demo_accounts",
                "explanation": "按 A 选项生成 SQL",
                "used_notes": ["demo_accounts"],
            },
            "session_id": "hermes-session-1",
        }

    monkeypatch.setattr(workbench_service, "iter_hermes_session_json", fake_iter_hermes_session_json)

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
        table = SchemaTable(datasource_id=ds.id, name="demo_accounts", original_comment="账户表")
        session.add(table)
        session.commit()
        session.refresh(table)
        session.add(SchemaField(table_id=table.id, name="id", type="BIGINT", original_comment="账户ID"))
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
    assert "retrieving_schema" in stream
    assert "SELECT * FROM demo_accounts" in stream
    assert "hermes-session-1" in stream
