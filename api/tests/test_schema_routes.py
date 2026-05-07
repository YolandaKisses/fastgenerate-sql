from fastapi.testclient import TestClient
import sqlalchemy

from app.main import app
from app.core import database
from app.api.deps import get_current_user
from app.models.user import AppUser


def override_current_user() -> AppUser:
    return AppUser(
        id=1,
        user_id="test-admin",
        name="Test Admin",
        account="admin",
        password_hash="unused",
        password_salt="unused",
        role="admin",
        is_active=True,
    )


def test_deprecated_knowledge_sync_stream_route_is_removed():
    app.dependency_overrides[get_current_user] = override_current_user
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/schema/knowledge/sync_stream/1",
        )
    app.dependency_overrides.clear()

    assert response.status_code == 404


def test_knowledge_sync_rejects_invalid_mode():
    app.dependency_overrides[get_current_user] = override_current_user
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/schema/knowledge/sync/1",
            json={"mode": "invalid_mode"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "不支持的同步模式: invalid_mode"


def test_ensure_compatible_schema_ignores_readonly_sqlite_migration(monkeypatch):
    class FakeResult:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

    class FakeConnection:
        def execute(self, statement):
            sql = str(statement)
            if "PRAGMA table_info(auditlog)" in sql:
                return FakeResult([(0, "id")])
            if "ALTER TABLE" in sql:
                raise sqlalchemy.exc.OperationalError(
                    "ALTER TABLE knowledgesynctask ADD COLUMN scope VARCHAR DEFAULT 'datasource'",
                    (),
                    Exception("attempt to write a readonly database"),
                )
            raise AssertionError(f"unexpected SQL: {sql}")

    class FakeBegin:
        def __enter__(self):
            return FakeConnection()

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeEngine:
        def begin(self):
            return FakeBegin()

    monkeypatch.setattr(database, "engine", FakeEngine())

    database.ensure_compatible_schema()
