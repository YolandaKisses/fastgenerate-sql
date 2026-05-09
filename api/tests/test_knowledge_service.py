from app.models.datasource import DataSource, SyncStatus
from app.models.knowledge import (
    KnowledgeSyncMode,
    KnowledgeSyncScope,
    KnowledgeSyncTask,
    KnowledgeSyncTaskStatus,
)
from app.models.routine import RoutineDefinition
from app.models.schema import SchemaTable
from app.services import knowledge_service
from sqlmodel import SQLModel, Session, create_engine
from pathlib import Path


def test_format_bullet_section_splits_numbered_text():
    lines = knowledge_service.format_bullet_section("1. 第一项 2. 第二项")

    assert lines == ["- 第一项", "- 第二项"]


def test_generate_table_summary_retries_on_non_json_hermes_output(monkeypatch):
    calls = {"count": 0}
    setting_calls = {"count": 0}

    class FakeExecResult:
        def all(self):
            return []

    class FakeSession:
        def exec(self, _statement):
            return FakeExecResult()

    def fake_run(prompt: str, cwd: str | None = None, hermes_cli_path: str | None = None):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("Hermes 返回了非 JSON 内容: {broken")
        return {
            "purpose": "用途",
            "core_fields": "字段",
            "relationships": "关系",
            "graph_links": [],
            "note_properties": {"summary": "摘要"},
            "caveats": "注意事项",
        }

    def fake_get_setting(session, key: str, default: str):
        setting_calls["count"] += 1
        return default

    monkeypatch.setattr(knowledge_service, "run_hermes_json", fake_run)
    monkeypatch.setattr(knowledge_service.setting_service, "get_setting", fake_get_setting)

    result = knowledge_service.generate_table_summary(
        session=FakeSession(),
        datasource=DataSource(
            id=1,
            name="demo",
            db_type="mysql",
            host="localhost",
            port=3306,
            database="demo",
            username="root",
            password="secret",
            sync_status=SyncStatus.SYNC_SUCCESS,
        ),
        table=type("Table", (), {"id": 1, "name": "users", "original_comment": "", "supplementary_comment": "", "related_tables": None})(),
        fields=[],
    )

    assert calls["count"] == 2
    assert setting_calls["count"] == 1
    assert result["purpose"] == "用途"


def test_finalize_failed_knowledge_task_preserves_detailed_error():
    task = KnowledgeSyncTask(
        datasource_id=1,
        datasource_name="demo",
        total_tables=4,
        completed_tables=0,
        failed_tables=4,
        output_root="/tmp",
        output_dir="/tmp/demo",
        error_message="表 user_login_logs 生成失败: name 're' is not defined",
    )
    datasource = DataSource(
        id=1,
        name="demo",
        db_type="mysql",
        host="localhost",
        port=3306,
        database="demo",
        username="root",
        password="secret",
    )

    knowledge_service.finalize_knowledge_task_status(task, datasource, total_tables=4)

    assert task.status == KnowledgeSyncTaskStatus.FAILED
    assert task.error_message == "表 user_login_logs 生成失败: name 're' is not defined"
    assert task.last_message == "表 user_login_logs 生成失败: name 're' is not defined"
    assert datasource.sync_status == SyncStatus.SYNC_FAILED


def test_finalize_partial_knowledge_task_keeps_specific_error_context():
    task = KnowledgeSyncTask(
        datasource_id=1,
        datasource_name="demo",
        total_tables=4,
        completed_tables=3,
        failed_tables=1,
        output_root="/tmp",
        output_dir="/tmp/demo",
        error_message="表 user_profiles 生成失败: Hermes 返回了非 JSON 内容",
    )
    datasource = DataSource(
        id=1,
        name="demo",
        db_type="mysql",
        host="localhost",
        port=3306,
        database="demo",
        username="root",
        password="secret",
    )

    knowledge_service.finalize_knowledge_task_status(task, datasource, total_tables=4)

    assert task.status == KnowledgeSyncTaskStatus.PARTIAL_SUCCESS
    assert task.error_message == "部分完成：1 张表失败；表 user_profiles 生成失败: Hermes 返回了非 JSON 内容"
    assert task.last_message == task.error_message
    assert datasource.last_sync_message == task.error_message


def test_validate_sync_mode_accepts_known_values():
    assert knowledge_service.validate_sync_mode("basic") == KnowledgeSyncMode.BASIC
    assert knowledge_service.validate_sync_mode("ai_enhanced") == KnowledgeSyncMode.AI_ENHANCED


def test_validate_sync_mode_rejects_invalid_value():
    try:
        knowledge_service.validate_sync_mode("invalid_mode")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert str(exc) == "不支持的同步模式: invalid_mode"


def test_reuse_active_task_only_when_signature_matches():
    matching_task = KnowledgeSyncTask(
        datasource_id=1,
        datasource_name="demo",
        scope=KnowledgeSyncScope.TABLE,
        mode=KnowledgeSyncMode.AI_ENHANCED,
        target_table_id=10,
        output_root="/tmp",
        output_dir="/tmp/demo",
    )
    assert knowledge_service.reuse_or_reject_active_task(
        matching_task,
        scope=KnowledgeSyncScope.TABLE,
        mode=KnowledgeSyncMode.AI_ENHANCED,
        target_table_id=10,
    ) is matching_task


def test_reuse_active_task_rejects_conflicting_signature():
    active_task = KnowledgeSyncTask(
        datasource_id=1,
        datasource_name="demo",
        scope=KnowledgeSyncScope.DATASOURCE,
        mode=KnowledgeSyncMode.BASIC,
        target_table_id=None,
        output_root="/tmp",
        output_dir="/tmp/demo",
    )

    try:
        knowledge_service.reuse_or_reject_active_task(
            active_task,
            scope=KnowledgeSyncScope.TABLE,
            mode=KnowledgeSyncMode.AI_ENHANCED,
            target_table_id=10,
        )
        assert False, "expected ValueError"
    except ValueError as exc:
        assert str(exc) == "当前数据源已有知识库同步任务进行中，请稍后再试"


def test_knowledge_task_payload_includes_scope_and_mode():
    task = KnowledgeSyncTask(
        datasource_id=1,
        datasource_name="demo",
        scope=KnowledgeSyncScope.TABLE,
        mode=KnowledgeSyncMode.AI_ENHANCED,
        output_root="/tmp",
        output_dir="/tmp/demo",
    )

    payload = knowledge_service.knowledge_task_payload(task)

    assert payload["scope"] == KnowledgeSyncScope.TABLE
    assert payload["mode"] == KnowledgeSyncMode.AI_ENHANCED


def test_generate_table_summary_basic_deduplicates_caveat_categories():
    table = type(
        "Table",
        (),
        {"name": "orders", "original_comment": "", "supplementary_comment": "", "related_tables": None},
    )()
    fields = [
        type("Field", (), {"name": "created_at", "original_comment": "", "supplementary_comment": ""})(),
        type("Field", (), {"name": "updated_at", "original_comment": "", "supplementary_comment": ""})(),
        type("Field", (), {"name": "biz_date", "original_comment": "", "supplementary_comment": ""})(),
    ]

    summary = knowledge_service.generate_table_summary_basic(table, fields)

    assert summary["caveats"] == "表中包含时间相关字段，请确认统计口径、时区以及应使用的业务时间字段。"


def test_generate_table_summary_basic_does_not_treat_status_as_time_field():
    table = type(
        "Table",
        (),
        {"name": "orders", "original_comment": "", "supplementary_comment": "", "related_tables": None},
    )()
    fields = [
        type("Field", (), {"name": "status", "original_comment": "", "supplementary_comment": ""})(),
        type("Field", (), {"name": "category", "original_comment": "", "supplementary_comment": ""})(),
        type("Field", (), {"name": "platform", "original_comment": "", "supplementary_comment": ""})(),
    ]

    summary = knowledge_service.generate_table_summary_basic(table, fields)

    assert "时间相关字段" not in summary["caveats"]
    assert "状态或类型字段" in summary["caveats"]


def test_get_related_routines_for_table_matches_definition_text_case_insensitively():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            RoutineDefinition(
                datasource_id=1,
                owner="APP",
                name="P_SYNC_USERS",
                routine_type="PROCEDURE",
                definition_text="SELECT * FROM USERS u JOIN orders o ON o.user_id = u.id",
            )
        )
        session.add(
            RoutineDefinition(
                datasource_id=1,
                owner="APP",
                name="P_CLEANUP",
                routine_type="PROCEDURE",
                definition_text="DELETE FROM audit_logs WHERE created_at < SYSDATE - 30",
            )
        )
        session.commit()

        table = SchemaTable(datasource_id=1, name="users")
        matched = knowledge_service.get_related_routines_for_table(session, datasource_id=1, table=table)

        assert [item.name for item in matched] == ["P_SYNC_USERS"]


def test_generate_table_summary_prompt_includes_related_routines_section(monkeypatch):
    captured = {"prompt": ""}

    def fake_run(prompt: str, cwd: str | None = None, hermes_cli_path: str | None = None):
        captured["prompt"] = prompt
        return {
            "purpose": "用途",
            "core_fields": "字段",
            "relationships": "关系",
            "graph_links": [],
            "note_properties": {"summary": "摘要"},
            "caveats": "注意事项",
        }

    monkeypatch.setattr(knowledge_service, "run_hermes_json", fake_run)
    monkeypatch.setattr(
        knowledge_service.setting_service,
        "get_setting",
        lambda session, key, default: default,
    )

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        datasource = DataSource(
            id=1,
            name="demo",
            db_type="oracle",
            host="localhost",
            port=1521,
            database="orclpdb",
            username="system",
            password="secret",
            sync_status=SyncStatus.SYNC_SUCCESS,
        )
        session.add(
            RoutineDefinition(
                datasource_id=1,
                owner="APP",
                name="P_SYNC_USERS",
                routine_type="PROCEDURE",
                definition_text="SELECT * FROM users WHERE users.id IS NOT NULL",
            )
        )
        session.add(
            SchemaTable(
                datasource_id=1,
                name="orders",
                original_comment="订单表",
            )
        )
        session.commit()

        knowledge_service.generate_table_summary(
            session=session,
            datasource=datasource,
            table=type(
                "Table",
                (),
                {
                    "id": 1,
                    "name": "users",
                    "original_comment": "用户表",
                    "supplementary_comment": "核心账户主体",
                    "related_tables": None,
                },
            )(),
            fields=[],
        )

    assert "高相关其他表" in captured["prompt"]
    assert "相关存储过程摘要" in captured["prompt"]
    assert "相关存储过程关键片段" in captured["prompt"]
    assert "APP.P_SYNC_USERS｜PROCEDURE" in captured["prompt"]
    assert "当前表角色:" in captured["prompt"]
    assert "SELECT * FROM users WHERE users.id IS NOT NULL" in captured["prompt"]
    assert "原文:" not in captured["prompt"]
    assert '所有字符串中禁止使用英文双引号' in captured["prompt"]
    assert "举例时用单引号、中文书名号或直接不用引号" in captured["prompt"]


def test_select_high_relevance_sibling_tables_prioritizes_manual_and_routine_hits():
    current_table = SchemaTable(
        datasource_id=1,
        name="sys_user",
        related_tables='{"sys_user_role":"通过用户ID关联角色","sys_dept":"机构归属"}',
    )
    siblings = [
        SchemaTable(datasource_id=1, name="sys_user_role", original_comment="用户-角色关联表"),
        SchemaTable(datasource_id=1, name="sys_dept", original_comment="部门信息表"),
        SchemaTable(datasource_id=1, name="tmp_noise", original_comment="临时表"),
    ]
    routines = [
        RoutineDefinition(
            datasource_id=1,
            owner="APP",
            name="P_SYNC_USERS",
            routine_type="PROCEDURE",
            definition_text="SELECT * FROM sys_user u JOIN sys_user_role r ON r.f_userid = u.f_userid",
        )
    ]

    selected = knowledge_service.select_high_relevance_sibling_tables(
        current_table=current_table,
        siblings=siblings,
        fields=[],
        related_routines=routines,
    )

    assert [table.name for table in selected] == ["sys_user_role", "sys_dept", "tmp_noise"]


def test_select_high_relevance_sibling_tables_uses_field_tokens_for_scoring():
    current_table = SchemaTable(
        datasource_id=1,
        name="trade_detail",
        related_tables=None,
    )
    siblings = [
        SchemaTable(datasource_id=1, name="user_profile", original_comment="用户信息"),
        SchemaTable(datasource_id=1, name="misc_config", original_comment="配置表"),
    ]
    fields = [
        type("Field", (), {"name": "user_id"})(),
        type("Field", (), {"name": "trade_date"})(),
    ]

    selected = knowledge_service.select_high_relevance_sibling_tables(
        current_table=current_table,
        siblings=siblings,
        fields=fields,
        related_routines=[],
    )

    assert [table.name for table in selected] == ["user_profile", "misc_config"]


def test_generate_table_summary_returns_routine_evidence_metadata(monkeypatch):
    monkeypatch.setattr(
        knowledge_service,
        "run_hermes_json",
        lambda prompt, cwd=None, hermes_cli_path=None: {
            "purpose": "用途",
            "core_fields": "字段",
            "relationships": "关系",
            "graph_links": [],
            "note_properties": {"summary": "摘要"},
            "caveats": "注意事项",
        },
    )
    monkeypatch.setattr(
        knowledge_service.setting_service,
        "get_setting",
        lambda session, key, default: default,
    )

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        datasource = DataSource(
            id=1,
            name="demo",
            db_type="oracle",
            host="localhost",
            port=1521,
            database="orclpdb",
            username="system",
            password="secret",
            sync_status=SyncStatus.SYNC_SUCCESS,
        )
        session.add(
            RoutineDefinition(
                datasource_id=1,
                owner="APP",
                name="P_SYNC_USERS",
                routine_type="PROCEDURE",
                definition_text=(
                    "CREATE OR REPLACE PROCEDURE P_SYNC_USERS AS\n"
                    "BEGIN\n"
                    "  SELECT * FROM users u JOIN orders o ON o.user_id = u.id;\n"
                    "END;"
                ),
            )
        )
        session.commit()

        summary = knowledge_service.generate_table_summary(
            session=session,
            datasource=datasource,
            table=type(
                "Table",
                (),
                {
                    "id": 1,
                    "name": "users",
                    "original_comment": "用户表",
                    "supplementary_comment": "",
                    "related_tables": None,
                },
            )(),
            fields=[],
        )

    assert len(summary["routine_evidence"]) == 1
    evidence = summary["routine_evidence"][0]
    assert evidence["name"] == "P_SYNC_USERS"
    assert evidence["owner"] == "APP"
    assert "SELECT * FROM users u JOIN orders o ON o.user_id = u.id;" in evidence["snippet"]


def test_generate_table_summary_ignores_optional_derivative_page_metadata(monkeypatch):
    monkeypatch.setattr(
        knowledge_service,
        "run_hermes_json",
        lambda prompt, cwd=None, hermes_cli_path=None: {
            "purpose": "用途",
            "core_fields": "字段",
            "relationships": "关系",
            "graph_links": [],
            "note_properties": {"summary": "摘要"},
            "caveats": "注意事项",
            "terms": [
                {
                    "name": "活跃用户",
                    "definition": "最近 30 天内有登录或下单行为的用户。",
                    "aliases": ["active user"],
                    "confidence": "高",
                    "evidence": "来自业务补充备注",
                }
            ],
            "metrics": [
                {
                    "name": "DAU",
                    "definition": "按天统计的活跃用户数。",
                    "formula_hint": "count(distinct user_id)",
                    "grain": "天",
                    "dimensions": ["渠道"],
                    "filters": "排除测试账号",
                    "time_field": "last_login_at",
                    "confidence": "中",
                    "evidence": "字段备注与业务补充",
                }
            ],
            "join_patterns": [
                {
                    "name": "用户关联订单",
                    "left_table": "users",
                    "right_table": "orders",
                    "join_condition": "orders.user_id = users.id",
                    "usage": "查看用户下单情况",
                    "confidence": "高",
                    "evidence": "字段命名与业务常识",
                }
            ],
        },
    )
    monkeypatch.setattr(
        knowledge_service.setting_service,
        "get_setting",
        lambda session, key, default: default,
    )

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        datasource = DataSource(
            id=1,
            name="demo",
            db_type="oracle",
            host="localhost",
            port=1521,
            database="orclpdb",
            username="system",
            password="secret",
            sync_status=SyncStatus.SYNC_SUCCESS,
        )
        summary = knowledge_service.generate_table_summary(
            session=session,
            datasource=datasource,
            table=type(
                "Table",
                (),
                {
                    "id": 1,
                    "name": "users",
                    "original_comment": "用户表",
                    "supplementary_comment": "核心账户主体",
                    "related_tables": None,
                },
            )(),
            fields=[],
        )

    assert "terms" not in summary
    assert "metrics" not in summary
    assert "join_patterns" not in summary


def test_run_knowledge_sync_task_only_writes_table_pages_and_index(tmp_path, monkeypatch):
    monkeypatch.setattr(
        knowledge_service,
        "run_hermes_json",
        lambda prompt, cwd=None, hermes_cli_path=None: {
            "purpose": "用户主体信息。",
            "core_fields": "user_id 表示用户主键。",
            "relationships": "users 可通过 user_id 关联 orders。",
            "graph_links": [
                {
                    "target_table": "orders",
                    "relation_type": "一对多",
                    "join_hint": "orders.user_id = users.id",
                    "confidence": "高",
                    "reason": "订单表通过 user_id 关联用户",
                }
            ],
            "note_properties": {
                "summary": "用户基础信息表",
                "primary_entities": ["活跃用户"],
                "keywords": ["用户域"],
            },
            "caveats": "统计时确认是否排除测试用户。",
            "terms": [
                {
                    "name": "活跃用户",
                    "definition": "最近 30 天内产生关键行为的用户。",
                    "aliases": ["active user"],
                    "confidence": "高",
                    "evidence": "业务补充备注",
                }
            ],
            "metrics": [
                {
                    "name": "DAU",
                    "definition": "每日活跃用户数。",
                    "formula_hint": "count(distinct user_id)",
                    "grain": "天",
                    "dimensions": ["渠道"],
                    "filters": "排除测试账号",
                    "time_field": "last_login_at",
                    "confidence": "中",
                    "evidence": "字段与备注",
                }
            ],
            "join_patterns": [
                {
                    "name": "用户关联订单",
                    "left_table": "users",
                    "right_table": "orders",
                    "join_condition": "orders.user_id = users.id",
                    "usage": "查询用户订单明细",
                    "confidence": "高",
                    "evidence": "graph link",
                }
            ],
        },
    )
    monkeypatch.setattr(
        knowledge_service.setting_service,
        "get_setting",
        lambda session, key, default: default,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    output_root = tmp_path / "vault"
    output_dir = output_root / "demo"

    with Session(engine) as session:
        session.add(
            DataSource(
                id=1,
                name="demo",
                db_type="oracle",
                host="localhost",
                port=1521,
                database="orclpdb",
                username="system",
                user_id="user-1",
                password="secret",
            )
        )
        session.add(SchemaTable(id=1, datasource_id=1, name="users", original_comment="用户表"))
        session.add(SchemaTable(id=2, datasource_id=1, name="orders", original_comment="订单表"))
        session.add(
            RoutineDefinition(
                datasource_id=1,
                owner="APP",
                name="P_SYNC_USERS",
                routine_type="PROCEDURE",
                definition_text="SELECT * FROM users u JOIN orders o ON o.user_id = u.id;",
            )
        )
        task = KnowledgeSyncTask(
            datasource_id=1,
            datasource_name="demo",
            status=KnowledgeSyncTaskStatus.PENDING,
            scope=KnowledgeSyncScope.DATASOURCE,
            mode=KnowledgeSyncMode.AI_ENHANCED,
            total_tables=2,
            output_root=str(output_root),
            output_dir=str(output_dir),
        )
        session.add(task)
        session.commit()
        task_id = task.id

    knowledge_service.run_knowledge_sync_task(engine, task_id)

    assert (output_dir / "tables" / "users.md").exists()
    assert (output_dir / "tables" / "orders.md").exists()
    assert (output_dir / "index.md").exists()
    assert not (output_dir / "routines").exists()
    assert not (output_dir / "terms").exists()
    assert not (output_dir / "metrics").exists()
    assert not (output_dir / "join_patterns").exists()


def test_single_table_sync_index_only_lists_generated_table(tmp_path, monkeypatch):
    monkeypatch.setattr(
        knowledge_service,
        "run_hermes_json",
        lambda prompt, cwd=None, hermes_cli_path=None: {
            "purpose": "用户主体信息。",
            "core_fields": "user_id 表示用户主键。",
            "relationships": "users 可通过 user_id 关联 orders。",
            "graph_links": [
                {
                    "target_table": "orders",
                    "relation_type": "一对多",
                    "join_hint": "orders.user_id = users.id",
                    "confidence": "高",
                    "reason": "订单表通过 user_id 关联用户",
                }
            ],
            "note_properties": {"summary": "用户基础信息表"},
            "caveats": "统计时确认是否排除测试用户。",
            "terms": [],
            "metrics": [],
            "join_patterns": [],
        },
    )
    monkeypatch.setattr(
        knowledge_service.setting_service,
        "get_setting",
        lambda session, key, default: default,
    )

    engine = create_engine(f"sqlite:///{tmp_path / 'single.db'}")
    SQLModel.metadata.create_all(engine)
    output_root = tmp_path / "vault"
    output_dir = output_root / "demo"

    with Session(engine) as session:
        session.add(
            DataSource(
                id=1,
                name="demo",
                db_type="oracle",
                host="localhost",
                port=1521,
                database="orclpdb",
                username="system",
                user_id="user-1",
                password="secret",
            )
        )
        session.add(SchemaTable(id=1, datasource_id=1, name="users", original_comment="用户表"))
        session.add(SchemaTable(id=2, datasource_id=1, name="orders", original_comment="订单表"))
        task = KnowledgeSyncTask(
            datasource_id=1,
            datasource_name="demo",
            status=KnowledgeSyncTaskStatus.PENDING,
            scope=KnowledgeSyncScope.TABLE,
            mode=KnowledgeSyncMode.AI_ENHANCED,
            target_table_id=1,
            total_tables=1,
            output_root=str(output_root),
            output_dir=str(output_dir),
        )
        session.add(task)
        session.commit()
        task_id = task.id

    knowledge_service.run_knowledge_sync_task(engine, task_id)

    index_text = (output_dir / "index.md").read_text(encoding="utf-8")
    assert "[[tables/users|users]]" in index_text
    assert "[[tables/orders|orders]]" not in index_text


def test_single_table_sync_does_not_emit_broken_table_wikilinks():
    datasource = DataSource(
        id=1,
        name="demo",
        db_type="oracle",
        host="localhost",
        port=1521,
        database="orclpdb",
        username="system",
        user_id="user-1",
        password="secret",
    )
    table = SchemaTable(
        datasource_id=1,
        name="users",
        original_comment="用户表",
        supplementary_comment="账户主体",
    )

    markdown = knowledge_service.render_table_markdown(
        datasource=datasource,
        table=table,
        fields=[],
        summary={
            "purpose": "用途",
            "relationships": "关系",
            "graph_links": [
                {
                    "target_table": "orders",
                    "relation_type": "一对多",
                    "join_hint": "orders.user_id = users.id",
                    "confidence": "高",
                    "reason": "订单表通过 user_id 关联用户",
                }
            ],
            "core_fields": "核心字段",
            "caveats": "注意事项",
            "routine_evidence": [],
        },
        existing_table_links={"users"},
    )

    assert "[[orders]]" not in markdown
    assert "orders · 一对多" in markdown


def test_join_pattern_frontmatter_related_uses_existing_table_paths_only():
    datasource = DataSource(
        id=1,
        name="demo",
        db_type="oracle",
        host="localhost",
        port=1521,
        database="orclpdb",
        username="system",
        user_id="user-1",
        password="secret",
    )

    markdown = knowledge_service.render_join_pattern_markdown(
        datasource=datasource,
        join_pattern={
            "name": "获取原始产-表关系",
            "left_table": "mdm_proc_table_physics",
            "right_table": "mdm_proc_table",
            "join_condition": "a.id = b.id",
            "usage": "查看产表关系",
            "confidence": "高",
            "evidence": "过程原文",
        },
        existing_table_links={"mdm_proc_table_physics"},
    )

    assert '[[tables/mdm_proc_table_physics|mdm_proc_table_physics]]' in markdown
    assert '[[tables/mdm_proc_table|mdm_proc_table]]' not in markdown
    assert '"[[mdm_proc_table]]"' not in markdown


def test_routine_related_uses_existing_table_paths_only():
    datasource = DataSource(
        id=1,
        name="demo",
        db_type="oracle",
        host="localhost",
        port=1521,
        database="orclpdb",
        username="system",
        user_id="user-1",
        password="secret",
    )
    routine = RoutineDefinition(
        datasource_id=1,
        owner="APP",
        name="P_DEMO",
        routine_type="PROCEDURE",
        definition_text="select 1 from dual",
    )

    markdown = knowledge_service.render_routine_markdown(
        datasource=datasource,
        routine=routine,
        related_tables=["mdm_proc_table_physics", "mdm_object"],
        existing_table_links={"mdm_proc_table_physics"},
    )

    assert '[[tables/mdm_proc_table_physics|mdm_proc_table_physics]]' in markdown
    assert '[[tables/mdm_object|mdm_object]]' not in markdown
    assert '"[[mdm_object]]"' not in markdown
    assert "- mdm_object" in markdown


def test_render_table_markdown_includes_routine_evidence_sections():
    datasource = DataSource(
        id=1,
        name="demo",
        db_type="oracle",
        host="localhost",
        port=1521,
        database="orclpdb",
        username="system",
        password="secret",
    )
    table = SchemaTable(
        datasource_id=1,
        name="users",
        original_comment="用户表",
        supplementary_comment="账户主体",
    )
    markdown = knowledge_service.render_table_markdown(
        datasource=datasource,
        table=table,
        fields=[],
        summary={
            "purpose": "用途",
            "relationships": "关系",
            "graph_links": [],
            "core_fields": "核心字段",
            "caveats": "注意事项",
            "routine_evidence": [
                {
                    "owner": "APP",
                    "name": "P_SYNC_USERS",
                    "routine_type": "PROCEDURE",
                    "snippet": "SELECT * FROM users;",
                }
            ],
        },
    )

    assert "## 相关存储过程" in markdown
    assert "- **证据来源**: Oracle 存储过程/函数同步原文" in markdown
    assert "- `APP.P_SYNC_USERS` · `PROCEDURE`" in markdown
    assert "### `APP.P_SYNC_USERS`" in markdown
    assert "```sql" in markdown
    assert "SELECT * FROM users;" in markdown


def test_render_table_markdown_always_shows_routine_section_and_strips_nohit_caveat():
    datasource = DataSource(
        id=1,
        name="demo",
        db_type="oracle",
        host="localhost",
        port=1521,
        database="orclpdb",
        username="system",
        password="secret",
    )
    table = SchemaTable(datasource_id=1, name="sys_user", original_comment="用户表")

    markdown = knowledge_service.render_table_markdown(
        datasource=datasource,
        table=table,
        fields=[],
        summary={
            "purpose": "用途",
            "relationships": "关系",
            "graph_links": [],
            "core_fields": "核心字段",
            "caveats": "密码字段需确认。未命中任何存储过程原文，上下游调用关系无法验证。",
            "routine_evidence": [],
        },
    )

    assert "## 相关存储过程" in markdown
    assert "- **证据来源**: Oracle 存储过程/函数同步原文" in markdown
    assert "- 暂无命中过程" in markdown
    assert "未命中任何存储过程原文" not in markdown.split("## 注意事项", 1)[1].split("## 相关存储过程", 1)[0]


def test_format_knowledge_timing_log_includes_sorted_metadata():
    line = knowledge_service.format_knowledge_timing_log(
        task_id=42,
        table_name="users",
        stage="hermes_call",
        elapsed_ms=1234.56,
        extra={"prompt_len": 2048, "routine_count": 2},
    )

    assert "task=42" in line
    assert "table=users" in line
    assert "stage=hermes_call" in line
    assert "elapsed_ms=1234.56" in line
    assert "prompt_len=2048" in line
    assert "routine_count=2" in line


def test_append_knowledge_timing_log_writes_to_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(knowledge_service.settings, "DATA_DIR", str(tmp_path))

    knowledge_service.append_knowledge_timing_log(
        task_id=7,
        table_name="users",
        stage="hermes_call",
        elapsed_ms=321.0,
        extra={"prompt_len": 1024},
    )

    log_path = Path(tmp_path) / "knowledge_sync_timing.log"
    assert log_path.exists()
    content = log_path.read_text(encoding="utf-8")
    assert "task=7" in content
    assert "table=users" in content
    assert "stage=hermes_call" in content
    assert "prompt_len=1024" in content
