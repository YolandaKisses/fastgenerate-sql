import warnings

from fastapi.testclient import TestClient

from app.main import app


def test_health_checks_database_connection():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {
            "database": "ok",
        },
    }


def test_app_startup_uses_lifespan_without_on_event_deprecation_warning():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        with TestClient(app):
            pass

    assert not any("on_event is deprecated" in str(warning.message) for warning in caught)
