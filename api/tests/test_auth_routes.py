from fastapi.testclient import TestClient

from app.main import app
from app.core.security import encrypt_password_for_test


def test_public_key_is_available_without_token():
    client = TestClient(app)

    response = client.get("/api/v1/auth/public-key")

    assert response.status_code == 200
    assert response.json()["algorithm"] == "RSA-OAEP"
    assert "BEGIN PUBLIC KEY" in response.json()["public_key"]


def test_login_returns_token_and_current_user():
    with TestClient(app) as client:
        encrypted_password = encrypt_password_for_test("888888")

        response = client.post(
            "/api/v1/auth/login",
            json={"account": "admin", "password": encrypted_password},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["token"]
        assert body["token_type"] == "bearer"
        assert body["user"]["account"] == "admin"
        assert body["user"]["name"] == "系统管理员"

        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {body['token']}"})
        assert me.status_code == 200
        assert me.json()["account"] == "admin"


def test_login_rejects_wrong_password():
    with TestClient(app) as client:
        encrypted_password = encrypt_password_for_test("wrong")

        response = client.post(
            "/api/v1/auth/login",
            json={"account": "admin", "password": encrypted_password},
        )

        assert response.status_code == 401


def test_business_routes_require_token():
    with TestClient(app) as client:
        response = client.get("/api/v1/datasources/")

        assert response.status_code == 401
