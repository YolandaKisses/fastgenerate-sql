from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from app.api.deps import get_current_user
from app.core.database import get_session
from app.main import app
from app.models.datasource import DataSource
from app.models.routine import RoutineDefinition
from app.models.schema import SchemaTable
from app.models.user import AppUser
from app.models.view import ViewDefinition


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


def test_create_sql_file_datasource_requires_uploaded_files():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_session] = override_session

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/datasources/",
                data={
                    "name": "SQL 文件数据源",
                    "db_type": "oracle",
                    "source_mode": "sql_file",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "SQL 文件模式必须上传至少一个 .sql 文件"


def test_create_sql_file_datasource_rejects_json_request_without_multipart():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_session] = override_session

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/datasources/",
                json={
                    "name": "SQL 文件数据源",
                    "db_type": "oracle",
                    "source_mode": "sql_file",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "SQL 文件模式创建必须使用 multipart/form-data 并上传 .sql 文件"


def test_sql_file_datasource_parse_replaces_existing_metadata():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_session] = override_session

    schema_sql = """
    CREATE TABLE users (
      id NUMBER,
      name VARCHAR2(100)
    );

    CREATE OR REPLACE VIEW v_users AS
    SELECT id, name FROM users;
    """
    routine_sql = """
    CREATE OR REPLACE PROCEDURE sync_users AS
    BEGIN
      INSERT INTO user_snapshot
      SELECT id, name FROM users;
    END;
    /
    """
    replacement_sql = """
    CREATE TABLE accounts (
      account_id NUMBER
    );
    """

    try:
        with TestClient(app) as client:
            create_response = client.post(
                "/api/v1/datasources/",
                data={
                    "name": "SQL 文件数据源",
                    "db_type": "oracle",
                    "source_mode": "sql_file",
                },
                files=[
                    ("files", ("schema.sql", schema_sql, "application/sql")),
                    ("files", ("routine.sql", routine_sql, "application/sql")),
                ],
            )

            assert create_response.status_code == 200
            created = create_response.json()
            datasource_id = created["id"]
            assert created["source_mode"] == "sql_file"
            assert created["source_status"] == "file_uploaded"
            assert created["source_file_count"] == 2

            parse_response = client.post(f"/api/v1/datasources/{datasource_id}/parse-sql")
            assert parse_response.status_code == 200
            assert parse_response.json()["success"] is True

            upload_response = client.post(
                f"/api/v1/datasources/{datasource_id}/upload-sql",
                files=[
                    ("files", ("replacement.sql", replacement_sql, "application/sql")),
                ],
            )
            assert upload_response.status_code == 200
            assert upload_response.json()["source_status"] == "file_uploaded"
            assert upload_response.json()["source_file_count"] == 1

            reparse_response = client.post(
                f"/api/v1/datasources/{datasource_id}/parse-sql"
            )
            assert reparse_response.status_code == 200
            assert reparse_response.json()["success"] is True
    finally:
        app.dependency_overrides.clear()

    with Session(engine) as session:
        datasource = session.get(DataSource, datasource_id)
        tables = session.exec(
            select(SchemaTable).where(SchemaTable.datasource_id == datasource_id)
        ).all()
        views = session.exec(
            select(ViewDefinition).where(ViewDefinition.datasource_id == datasource_id)
        ).all()
        routines = session.exec(
            select(RoutineDefinition).where(RoutineDefinition.datasource_id == datasource_id)
        ).all()

    assert datasource is not None
    assert datasource.source_status == "parse_success"
    assert datasource.source_file_count == 1
    assert [table.name for table in tables] == ["accounts"]
    assert views == []
    assert routines == []
