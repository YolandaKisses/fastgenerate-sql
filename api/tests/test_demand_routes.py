from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from app.api.deps import get_current_user
from app.core.database import get_session
from app.main import app
from app.models.datasource import DataSource
from app.models.user import AppUser
from app.services import setting_service


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


def test_create_demand_document_route_writes_wiki_file(tmp_path: Path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            DataSource(
                id=1,
                name="监管ODS",
                db_type="mysql",
                host="localhost",
                port=3306,
                database="demo",
                username="root",
                password="secret",
                user_id="test-admin",
            )
        )
        session.commit()

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_session] = override_session

    original_get_setting = setting_service.get_setting
    setting_service.get_setting = lambda session, key, default=None: str(tmp_path) if key == "wiki_root" else original_get_setting(session, key, default)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/demand/documents",
                json={
                    "datasource_id": 1,
                    "demand_name": "east报送",
                    "table_name": "ads_east_report_detail",
                    "fields": [
                        {
                            "name": "report_date",
                            "type": "date",
                            "original_comment": "报送日期",
                            "supplementary_comment": "按自然日出数",
                        }
                    ],
                },
            )
    finally:
        setting_service.get_setting = original_get_setting
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["relative_path"] == "监管ODS/demand/east报送/ads_east_report_detail.md"
    assert Path(body["absolute_path"]).exists()
    assert "ads_east_report_detail" in body["content"]


def test_demand_category_routes_support_crud(tmp_path: Path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            DataSource(
                id=1,
                name="监管ODS",
                db_type="mysql",
                host="localhost",
                port=3306,
                database="demo",
                username="root",
                password="secret",
                user_id="test-admin",
            )
        )
        session.commit()

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_session] = override_session

    original_get_setting = setting_service.get_setting
    setting_service.get_setting = lambda session, key, default=None: str(tmp_path) if key == "wiki_root" else original_get_setting(session, key, default)

    try:
      with TestClient(app) as client:
        tree_response = client.get("/api/v1/demand/categories/1")
        create_response = client.post(
            "/api/v1/demand/categories",
            json={"datasource_id": 1, "name": "1104报送", "parent_path": "demand"},
        )
        rename_response = client.patch(
            "/api/v1/demand/categories",
            json={"datasource_id": 1, "path": "1104报送", "new_name": "1104报送-月报"},
        )
        delete_response = client.request(
            "DELETE",
            "/api/v1/demand/categories",
            json={"datasource_id": 1, "path": "1104报送-月报"},
        )
    finally:
        setting_service.get_setting = original_get_setting
        app.dependency_overrides.clear()

    assert tree_response.status_code == 200
    assert tree_response.json()["tree"]["key"] == "demand"
    assert tree_response.json()["tree"]["children"] == []
    assert tree_response.json()["default_key"] is None

    assert create_response.status_code == 200
    assert create_response.json()["key"] == "1104报送"

    assert rename_response.status_code == 200
    assert rename_response.json()["key"] == "1104报送-月报"

    assert delete_response.status_code == 200
    assert delete_response.json()["success"] is True


def test_list_demand_documents_route_returns_saved_tables(tmp_path: Path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            DataSource(
                id=1,
                name="监管ODS",
                db_type="mysql",
                host="localhost",
                port=3306,
                database="demo",
                username="root",
                password="secret",
                user_id="test-admin",
            )
        )
        session.commit()

    def override_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_session] = override_session

    original_get_setting = setting_service.get_setting
    setting_service.get_setting = lambda session, key, default=None: str(tmp_path) if key == "wiki_root" else original_get_setting(session, key, default)

    try:
        with TestClient(app) as client:
            client.post(
                "/api/v1/demand/categories",
                json={"datasource_id": 1, "name": "east报送", "parent_path": "demand"},
            )
            client.post(
                "/api/v1/demand/documents",
                json={
                    "datasource_id": 1,
                    "demand_name": "east报送",
                    "table_name": "ads_east_report_detail",
                    "table_comment": "EAST 明细报送表",
                    "fields": [
                        {
                            "name": "report_date",
                            "type": "date",
                            "original_comment": "报送日期",
                            "supplementary_comment": "按自然日出数",
                        }
                    ],
                },
            )
            response = client.get(
                "/api/v1/demand/documents/1?demand_name=east%E6%8A%A5%E9%80%81",
            )
    finally:
        setting_service.get_setting = original_get_setting
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["name"] == "ads_east_report_detail"
    assert payload[0]["comment"] == "EAST 明细报送表"
