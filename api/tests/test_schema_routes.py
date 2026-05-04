from fastapi.testclient import TestClient

from app.core.security import encrypt_password_for_test
from app.main import app


def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"account": "admin", "password": encrypt_password_for_test("888888")},
    )
    assert response.status_code == 200
    token = response.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_deprecated_knowledge_sync_stream_route_is_removed():
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/schema/knowledge/sync_stream/1",
            headers=auth_headers(client),
        )

    assert response.status_code == 404
