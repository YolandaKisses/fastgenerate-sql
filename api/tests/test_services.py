import unittest
from unittest.mock import MagicMock, patch

from sqlmodel import Session, SQLModel, create_engine, select

from app.models.audit_log import AuditLog
from app.models.datasource import DataSource, DataSourceStatus, DataSourceUpdate
from app.models.model_config import ModelConfig
from app.models.schema import SchemaField, SchemaTable
from app.services import datasource_service, workbench_service


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

    def create_model_config(self):
        config = ModelConfig(api_key="test-key", model_name="gpt-4o-mini")
        self.session.add(config)
        self.session.commit()
        return config

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

    def test_update_datasource_marks_stale_when_connection_fields_change(self):
        datasource = self.create_datasource(status=DataSourceStatus.CONNECTION_OK)

        updated = datasource_service.update_datasource(
            self.session,
            datasource.id,
            DataSourceUpdate(host="db.internal")
        )

        self.assertEqual(updated.status, DataSourceStatus.STALE)

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
        self.create_model_config()

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

        with patch("app.services.workbench_service.httpx.Client") as http_client:
            result = workbench_service.ask_llm(self.session, datasource.id, "销售额是多少")

        self.assertEqual(result["type"], "clarification")
        self.assertIn("销售额", result["message"])
        http_client.assert_not_called()

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


if __name__ == "__main__":
    unittest.main()
