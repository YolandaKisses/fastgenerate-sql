import unittest
from unittest.mock import MagicMock, patch
import tempfile
from pathlib import Path
from datetime import datetime

from sqlmodel import Session, SQLModel, create_engine, select

from app.models.audit_log import AuditLog
from app.models.datasource import DataSource, DataSourceStatus, DataSourceUpdate, SyncStatus
from app.models.knowledge import KnowledgeSyncTask, KnowledgeSyncTaskStatus
from app.models.schema import SchemaField, SchemaTable
from app.services import datasource_service, hermes_service, knowledge_service, workbench_service, schema_service


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        SQLModel.metadata.create_all(self.engine)
        self.session = Session(self.engine)

    def tearDown(self):
        self.session.close()
        self.engine.dispose()

    def create_datasource(self, **overrides):
        payload = {
            "name": "sales-db",
            "db_type": "mysql",
            "host": "127.0.0.1",
            "port": 3306,
            "database": "analytics",
            "username": "root",
            "password": "secret",
            "status": DataSourceStatus.CONNECTION_OK,
        }
        payload.update(overrides)
        ds = DataSource(**payload)
        self.session.add(ds)
        self.session.commit()
        self.session.refresh(ds)
        return ds

    def test_test_connection_supports_oracle(self):
        datasource = self.create_datasource(db_type="oracle", port=1521, database="orclpdb")

        fake_engine = MagicMock()
        fake_connection = MagicMock()
        fake_engine.connect.return_value.__enter__.return_value = fake_connection

        with patch("app.services.datasource_service.sqlalchemy.create_engine", return_value=fake_engine) as create_engine_mock:
            result = datasource_service.test_connection(datasource)

        self.assertTrue(result["success"])
        called_url = create_engine_mock.call_args.args[0]
        self.assertTrue(called_url.startswith("oracle+oracledb://"))
        self.assertIn("service_name=orclpdb", called_url)

    def test_test_connection_classifies_auth_failure(self):
        datasource = self.create_datasource()

        with patch("app.services.datasource_service.sqlalchemy.create_engine", side_effect=Exception("Access denied for user 'root'")):
            result = datasource_service.test_connection(datasource)

        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "auth_failed")
        self.assertIn("认证失败", result["message"])

    def test_update_datasource_marks_stale_when_connection_fields_change(self):
        datasource = self.create_datasource(status=DataSourceStatus.CONNECTION_OK)

        updated = datasource_service.update_datasource(
            self.session,
            datasource.id,
            DataSourceUpdate(host="db.internal")
        )

        self.assertEqual(updated.status, DataSourceStatus.STALE)

    def test_sync_schema_with_no_tables_does_not_mark_ready(self):
        datasource = self.create_datasource(status=DataSourceStatus.CONNECTION_OK)

        fake_inspector = MagicMock()
        fake_inspector.get_table_names.return_value = []

        with patch("app.services.schema_service.sqlalchemy.create_engine"):
            with patch("app.services.schema_service.sqlalchemy.inspect", return_value=fake_inspector):
                result = schema_service.sync_schema_for_datasource(self.session, datasource)

        self.session.refresh(datasource)
        self.assertFalse(result["success"])
        self.assertEqual(datasource.status, DataSourceStatus.SYNC_FAILED)
        self.assertEqual(datasource.sync_status, SyncStatus.SYNC_FAILED)

    def test_validate_sql_candidate_rejects_multi_statement(self):
        result = workbench_service.validate_sql_candidate("SELECT * FROM orders; DELETE FROM orders")
        self.assertEqual(result["status"], "invalid")
        self.assertTrue(result["reasons"])

    def test_delete_datasource_removes_schema_and_keeps_audit_logs(self):
        datasource = self.create_datasource()
        table = SchemaTable(datasource_id=datasource.id, name="orders")
        self.session.add(table)
        self.session.commit()
        self.session.refresh(table)

        field = SchemaField(table_id=table.id, name="amount", type="DECIMAL")
        log = AuditLog(datasource_id=datasource.id, datasource_name=datasource.name, question="销售额是多少")
        self.session.add(field)
        self.session.add(log)
        self.session.commit()

        result = datasource_service.delete_datasource(self.session, datasource.id)

        self.assertTrue(result["success"])
        self.assertIsNone(self.session.get(DataSource, datasource.id))
        self.assertEqual(len(self.session.exec(select(SchemaTable)).all()), 0)
        self.assertEqual(len(self.session.exec(select(SchemaField)).all()), 0)
        self.assertEqual(len(self.session.exec(select(AuditLog)).all()), 1)

    def test_ask_llm_short_circuits_with_clarification_for_ambiguous_question(self):
        datasource = self.create_datasource(status=DataSourceStatus.CONNECTION_OK)
        orders = SchemaTable(datasource_id=datasource.id, name="orders", supplementary_comment="订单销售额")
        refunds = SchemaTable(datasource_id=datasource.id, name="refunds", supplementary_comment="退款金额")
        self.session.add(orders)
        self.session.add(refunds)
        self.session.commit()
        self.session.refresh(orders)
        self.session.refresh(refunds)

        self.session.add(SchemaField(table_id=orders.id, name="amount", type="DECIMAL", supplementary_comment="销售额"))
        self.session.add(SchemaField(table_id=refunds.id, name="amount", type="DECIMAL", supplementary_comment="销售额"))
        self.session.commit()

        with patch("app.services.workbench_service.run_hermes_json") as hermes_runner:
            with patch("app.services.workbench_service.get_datasource_knowledge_dir", return_value=Path("/tmp/obsidian/sales/tables")):
                with patch("pathlib.Path.exists", return_value=True):
                    result = workbench_service.ask_llm(self.session, datasource.id, "销售额是多少")

        self.assertEqual(result["type"], "clarification")
        self.assertIn("销售额", result["message"])
        hermes_runner.assert_not_called()

    def test_ask_llm_requires_knowledge_notes(self):
        datasource = self.create_datasource(status=DataSourceStatus.CONNECTION_OK)

        with patch("app.services.workbench_service.get_datasource_knowledge_dir", return_value=Path("/tmp/missing-notes")):
            result = workbench_service.ask_llm(self.session, datasource.id, "销售额是多少")

        self.assertEqual(result["type"], "error")
        self.assertIn("知识库", result["message"])

    def test_ask_llm_uses_local_hermes_with_obsidian_context(self):
        datasource = self.create_datasource(status=DataSourceStatus.CONNECTION_OK)
        knowledge_dir = Path("/tmp/obsidian/FastGenerate SQL/sales/tables")

        with patch("app.services.workbench_service.run_hermes_json", return_value={
            "type": "sql_candidate",
            "sql": "SELECT amount FROM orders",
            "explanation": "查询订单销售额"
        }) as hermes_runner:
            with patch("app.services.workbench_service.get_datasource_knowledge_dir", return_value=knowledge_dir):
                with patch("pathlib.Path.exists", return_value=True):
                    result = workbench_service.ask_llm(self.session, datasource.id, "查询订单销售额")

        self.assertEqual(result["type"], "sql_candidate")
        self.assertEqual(result["sql"], "SELECT amount FROM orders")
        hermes_runner.assert_called_once()
        prompt_arg = hermes_runner.call_args.args[0]
        self.assertIn(str(knowledge_dir), prompt_arg)
        self.assertIn("Obsidian", prompt_arg)

    def test_ask_llm_returns_warning_when_audit_log_write_fails(self):
        datasource = self.create_datasource(status=DataSourceStatus.CONNECTION_OK)
        table = SchemaTable(datasource_id=datasource.id, name="orders", supplementary_comment="订单")
        self.session.add(table)
        self.session.commit()
        self.session.refresh(table)
        self.session.add(SchemaField(table_id=table.id, name="amount", type="DECIMAL", supplementary_comment="销售额"))
        self.session.commit()

        original_commit = self.session.commit
        commit_calls = {"count": 0}

        def flaky_commit():
            commit_calls["count"] += 1
            if commit_calls["count"] >= 1:
                raise RuntimeError("disk full")
            return original_commit()

        with patch("app.services.workbench_service.run_hermes_json", return_value={
            "type": "sql_candidate",
            "sql": "SELECT amount FROM orders",
            "explanation": "ok"
        }):
            with patch("app.services.workbench_service.get_datasource_knowledge_dir", return_value=Path("/tmp/obsidian/sales/tables")):
                with patch("pathlib.Path.exists", return_value=True):
                    with patch.object(self.session, "commit", side_effect=flaky_commit):
                        result = workbench_service.ask_llm(self.session, datasource.id, "查询订单销售额")

        self.assertEqual(result["type"], "sql_candidate")
        self.assertIn("warning", result)

    def test_execute_readonly_sql_returns_warning_when_audit_log_write_fails(self):
        datasource = self.create_datasource(db_type="mysql")
        self.session.add(AuditLog(datasource_id=datasource.id, datasource_name=datasource.name, question="q", sql="SELECT * FROM orders", executed=False))
        self.session.commit()

        fake_result = MagicMock()
        fake_result.keys.return_value = ["amount"]
        fake_result.fetchmany.return_value = [{"amount": 100}]

        fake_driver_connection = MagicMock()
        fake_sqlalchemy_connection = MagicMock()
        fake_sqlalchemy_connection.connection.driver_connection = fake_driver_connection
        fake_sqlalchemy_connection.execute.side_effect = [None, fake_result]

        fake_engine = MagicMock()
        fake_engine.connect.return_value.__enter__.return_value = fake_sqlalchemy_connection

        original_commit = self.session.commit
        commit_calls = {"count": 0}

        def flaky_commit():
            commit_calls["count"] += 1
            if commit_calls["count"] >= 1:
                raise RuntimeError("disk full")
            return original_commit()

        with patch("app.services.workbench_service.sqlalchemy.create_engine", return_value=fake_engine):
            with patch.object(self.session, "commit", side_effect=flaky_commit):
                result = workbench_service.execute_readonly_sql(self.session, datasource.id, "SELECT * FROM orders")

        self.assertEqual(result["status"], "success")
        self.assertIn("warning", result)

    def test_execute_readonly_sql_applies_mysql_limits_before_query(self):
        datasource = self.create_datasource(db_type="mysql")
        self.session.add(AuditLog(datasource_id=datasource.id, datasource_name=datasource.name, question="q", sql="SELECT * FROM orders", executed=False))
        self.session.commit()

        fake_result = MagicMock()
        fake_result.keys.return_value = ["amount"]
        fake_result.fetchmany.return_value = [{"amount": 100}]

        fake_driver_connection = MagicMock()
        fake_sqlalchemy_connection = MagicMock()
        fake_sqlalchemy_connection.connection.driver_connection = fake_driver_connection
        fake_sqlalchemy_connection.execute.side_effect = [None, fake_result]

        fake_engine = MagicMock()
        fake_engine.connect.return_value.__enter__.return_value = fake_sqlalchemy_connection

        with patch("app.services.workbench_service.sqlalchemy.create_engine", return_value=fake_engine):
            result = workbench_service.execute_readonly_sql(self.session, datasource.id, "SELECT * FROM orders")

        self.assertEqual(result["status"], "success")
        first_statement = str(fake_sqlalchemy_connection.execute.call_args_list[0].args[0])
        self.assertIn("MAX_EXECUTION_TIME=30000", first_statement)
        self.assertEqual(fake_driver_connection.call_timeout, 30000)

    def test_create_knowledge_sync_task(self):
        datasource = self.create_datasource(status=DataSourceStatus.READY)
        self.session.add(SchemaTable(datasource_id=datasource.id, name="orders", supplementary_comment="订单主表"))
        self.session.commit()

        task = knowledge_service.create_knowledge_sync_task(self.session, datasource.id)

        self.assertIsNotNone(task.id)
        self.assertEqual(task.datasource_id, datasource.id)
        self.assertEqual(task.datasource_name, datasource.name)
        self.assertEqual(task.status, KnowledgeSyncTaskStatus.PENDING)
        self.assertEqual(task.output_root, knowledge_service.get_obsidian_root_path())

    def test_create_knowledge_sync_task_requires_tables(self):
        datasource = self.create_datasource(status=DataSourceStatus.CONNECTION_OK)

        with self.assertRaises(ValueError) as context:
            knowledge_service.create_knowledge_sync_task(self.session, datasource.id)

        self.assertIn("未找到已同步表", str(context.exception))

    def test_generate_table_markdown(self):
        datasource = self.create_datasource(status=DataSourceStatus.READY, name="sales")
        table = SchemaTable(
            datasource_id=datasource.id,
            name="orders",
            original_comment="订单表",
            supplementary_comment="仅包含已支付订单"
        )
        self.session.add(table)
        self.session.commit()
        self.session.refresh(table)

        fields = [
            SchemaField(table_id=table.id, name="id", type="BIGINT", original_comment="主键", supplementary_comment="订单ID"),
            SchemaField(table_id=table.id, name="amount", type="DECIMAL", original_comment="金额", supplementary_comment="实付金额"),
        ]

        markdown = knowledge_service.render_table_markdown(
            datasource=datasource,
            table=table,
            fields=fields,
            summary={
                "purpose": "记录交易订单。",
                "core_fields": "id 用于唯一标识订单，amount 表示实付金额。",
                "relationships": "通常通过 user_id 与用户表关联。",
                "graph_links": [
                    {
                        "target_table": "users",
                        "relation_type": "维度关联",
                        "join_hint": "orders.user_id -> users.id",
                        "confidence": "高",
                        "reason": "字段命名明显对应用户主键"
                    }
                ],
                "note_properties": {
                    "type": "table-note",
                    "status": "active",
                    "tags": ["db-table", "sales"],
                    "summary": "订单主表，用于记录交易订单。",
                    "related": ["[[users]]"],
                    "domain": "交易",
                    "table_type": "事实表",
                    "primary_entities": ["订单", "用户"],
                    "keywords": ["订单", "收入"]
                },
                "caveats": "退款订单可能记录在其他表中。"
            },
            generated_at=datetime(2026, 4, 30, 11, 30, 0)
        )

        self.assertTrue(markdown.startswith("---\n"))
        self.assertIn("type: table-note", markdown)
        self.assertIn("status: active", markdown)
        self.assertIn("created: 2026/04/30", markdown)
        self.assertIn("updated: 2026/04/30", markdown)
        self.assertIn("summary: 订单主表，用于记录交易订单。", markdown)
        self.assertIn('- "[[users]]"', markdown)
        self.assertIn("- db-table", markdown)
        self.assertIn("# orders", markdown)
        self.assertIn("仅包含已支付订单", markdown)
        self.assertIn("记录交易订单。", markdown)
        self.assertIn("## 关联笔记", markdown)
        self.assertIn("## 常见关联关系", markdown)
        self.assertIn("- [[users]]", markdown)
        self.assertIn("`orders.user_id -> users.id`", markdown)
        self.assertIn("| amount | DECIMAL | 金额 | 实付金额 |", markdown)
        self.assertIn("[[../index|返回数据源总览]]", markdown)

    def test_run_knowledge_sync_task_writes_markdown_and_updates_status(self):
        datasource = self.create_datasource(status=DataSourceStatus.READY, name="sales/ops")
        table = SchemaTable(
            datasource_id=datasource.id,
            name="orders:paid",
            original_comment="订单表",
            supplementary_comment="已支付订单"
        )
        self.session.add(table)
        self.session.commit()
        self.session.refresh(table)
        self.session.add(SchemaField(table_id=table.id, name="amount", type="DECIMAL", original_comment="金额", supplementary_comment="实付金额"))
        self.session.commit()

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("app.services.knowledge_service.get_obsidian_root_path", return_value=temp_dir):
                task = knowledge_service.create_knowledge_sync_task(self.session, datasource.id)
                with patch("app.services.knowledge_service.generate_table_summary", return_value={
                    "purpose": "记录已支付订单。",
                    "core_fields": "amount 表示实付金额。",
                    "relationships": "可能与用户表关联。",
                    "caveats": "需注意退款场景。"
                }):
                    knowledge_service.run_knowledge_sync_task(self.engine, task.id)

            self.session.expire_all()
            refreshed = self.session.get(KnowledgeSyncTask, task.id)
            self.assertEqual(refreshed.status, KnowledgeSyncTaskStatus.COMPLETED)
            self.assertEqual(refreshed.completed_tables, 1)
            datasource_dir = Path(temp_dir) / "sales-ops"
            self.assertTrue((datasource_dir / "index.md").exists())
            self.assertTrue((datasource_dir / "tables" / "orders-paid.md").exists())

    def test_build_summary_prompt_emphasizes_business_wiki_output(self):
        datasource = self.create_datasource(status=DataSourceStatus.READY, name="sales")
        table = SchemaTable(
            datasource_id=datasource.id,
            name="orders",
            original_comment="订单表",
            supplementary_comment="仅包含已支付订单"
        )
        fields = [
            SchemaField(table_id=1, name="status", type="VARCHAR", original_comment="订单状态", supplementary_comment="枚举值: paid/refunded/cancelled"),
            SchemaField(table_id=1, name="amount", type="DECIMAL", original_comment="金额", supplementary_comment="口径: 实付金额"),
        ]

        prompt = knowledge_service._build_summary_prompt(datasource, table, fields)

        self.assertIn("业务用途", prompt)
        self.assertIn("统计口径", prompt)
        self.assertIn("枚举值", prompt)
        self.assertIn("置信度", prompt)
        self.assertIn("Obsidian", prompt)

    def test_generate_table_summary_uses_local_hermes(self):
        datasource = self.create_datasource(status=DataSourceStatus.READY, name="sales")
        table = SchemaTable(datasource_id=datasource.id, name="orders")
        fields = [SchemaField(table_id=1, name="amount", type="DECIMAL", original_comment="金额")]

        with patch("app.services.knowledge_service.run_hermes_json", return_value={
            "purpose": "用于分析已支付订单收入。",
            "core_fields": "amount 代表实付金额口径。",
            "relationships": "与用户表关联，置信度：中。",
            "caveats": "退款订单需结合退款表。"
        }) as hermes_runner:
            summary = knowledge_service.generate_table_summary(self.session, datasource, table, fields)

        self.assertEqual(summary["purpose"], "用于分析已支付订单收入。")
        hermes_runner.assert_called_once()

    def test_parse_hermes_json_output_accepts_code_fence(self):
        payload = hermes_service.parse_hermes_json_output("""```json
{"ok": true, "source": "hermes"}
```""")
        self.assertTrue(payload["ok"])

    def test_parse_hermes_json_output_repairs_newlines_inside_strings(self):
        payload = hermes_service.parse_hermes_json_output("""{
  "purpose": "用于登录分析",
  "core_fields": "id：主键
user_id：用户ID
login_status：登录状态",
  "relationships": "通过 user_id 关联用户表，置信度：高",
  "caveats": "注意失败重试"
}""")
        self.assertIn("user_id：用户ID", payload["core_fields"])


if __name__ == "__main__":
    unittest.main()
