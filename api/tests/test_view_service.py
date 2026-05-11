from sqlmodel import SQLModel, Session, create_engine, select

from app.models.datasource import DataSource
from app.models.view import ViewDefinition, ViewSqlFact
from app.services import view_service


class FakeOracleResult:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class FakeOracleConnection:
    def __init__(self, view_rows, comment_rows):
        self._view_rows = view_rows
        self._comment_rows = comment_rows

    def execute(self, statement):
        sql = str(statement)
        if "FROM all_views" in sql:
            return FakeOracleResult(self._view_rows)
        if "FROM all_tab_comments" in sql:
            return FakeOracleResult(self._comment_rows)
        raise AssertionError(f"unexpected SQL: {sql}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeOracleEngine:
    def __init__(self, view_rows, comment_rows):
        self._view_rows = view_rows
        self._comment_rows = comment_rows

    def connect(self):
        return FakeOracleConnection(self._view_rows, self._comment_rows)

    def dispose(self):
        return None


def test_sync_views_for_oracle_persists_definitions_and_facts(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    view_rows = [
        ("APP", "VW_USER_ORDER", "SELECT u.id, o.id AS order_id FROM users u JOIN orders o ON o.user_id = u.id"),
    ]
    comment_rows = [
        ("APP", "VW_USER_ORDER", "用户订单视图"),
    ]

    monkeypatch.setattr(
        view_service.sqlalchemy,
        "create_engine",
        lambda *args, **kwargs: FakeOracleEngine(view_rows, comment_rows),
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
        )
        session.add(ds)
        session.commit()
        session.refresh(ds)

        result = view_service.sync_views_for_datasource(session, ds)

        assert result["success"] is True
        views = session.exec(select(ViewDefinition)).all()
        facts = session.exec(select(ViewSqlFact).order_by(ViewSqlFact.table_name)).all()

        assert len(views) == 1
        assert views[0].name == "VW_USER_ORDER"
        assert views[0].original_comment == "用户订单视图"
        assert [(item.usage_type, item.table_name) for item in facts] == [
            ("read", "orders"),
            ("read", "users"),
        ]
