from app.models.datasource import DataSource, SyncStatus
from app.models.knowledge import (
    KnowledgeSyncMode,
    KnowledgeSyncScope,
    KnowledgeSyncTask,
    KnowledgeSyncTaskStatus,
)
from app.services import knowledge_service


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
        table=type("Table", (), {"id": 1, "name": "users", "original_comment": "", "supplementary_comment": ""})(),
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
        {"name": "orders", "original_comment": "", "supplementary_comment": ""},
    )()
    fields = [
        type("Field", (), {"name": "created_at", "original_comment": "", "supplementary_comment": ""})(),
        type("Field", (), {"name": "updated_at", "original_comment": "", "supplementary_comment": ""})(),
        type("Field", (), {"name": "biz_date", "original_comment": "", "supplementary_comment": ""})(),
    ]

    summary = knowledge_service.generate_table_summary_basic(table, fields)

    assert summary["caveats"] == "表中包含时间相关字段，请确认统计口径、时区以及应使用的业务时间字段。"
