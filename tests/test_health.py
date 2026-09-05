from app.core.config import settings


def test_liveness(client):
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_points_to_documentation(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["documentation"] == "/docs"


def test_management_routes_require_configured_api_key(client, monkeypatch):
    monkeypatch.setattr(settings, "api_key", "test-api-key")

    unauthorized = client.get("/projects")
    authorized = client.get(
        "/projects",
        headers={"X-API-Key": "test-api-key"},
    )

    assert unauthorized.status_code == 401
    assert authorized.status_code == 200
