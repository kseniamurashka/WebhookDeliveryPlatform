from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(autouse=True)
def disable_celery_task_publishing(monkeypatch):
    """API tests verify database state without requiring a Redis broker."""
    monkeypatch.setattr(
        "app.api.events.deliver_webhook.delay",
        lambda *args, **kwargs: None,
    )


@pytest.fixture
def project_factory(client):
    def create_project(name: str | None = None) -> str:
        response = client.post(
            "/projects",
            json={
                "name": name or f"Test Project {uuid4()}",
            },
        )

        assert response.status_code == 201

        return response.json()["id"]

    return create_project


@pytest.fixture
def endpoint_factory(client):
    def create_endpoint(
        project_id: str,
        url: str | None = None,
    ) -> str:
        response = client.post(
            "/endpoints",
            json={
                "project_id": project_id,
                "url": url or f"https://{uuid4()}.example.com/webhooks",
            },
        )

        assert response.status_code == 201

        return response.json()["id"]

    return create_endpoint


@pytest.fixture
def subscription_factory(client):
    def create_subscription(
        endpoint_id: str,
        event_type: str,
    ) -> str:
        response = client.post(
            "/subscriptions",
            json={
                "endpoint_id": endpoint_id,
                "event_type": event_type,
            },
        )

        assert response.status_code == 201

        return response.json()["id"]

    return create_subscription


@pytest.fixture
def event_factory(client):
    def create_event(
        project_id: str,
        event_type: str = "test.event",
        payload: dict | None = None,
    ) -> str:
        response = client.post(
            "/events",
            json={
                "project_id": project_id,
                "event_type": event_type,
                "payload": payload or {"hello": "world"},
            },
        )

        assert response.status_code == 201

        return response.json()["id"]

    return create_event


@pytest.fixture
def delivery_factory(
    client,
    project_factory,
    endpoint_factory,
    subscription_factory,
    event_factory,
):
    def create_delivery(
        endpoint_url: str = "https://example.com/webhook",
        event_type: str = "payment.completed",
    ) -> str:
        project_id = project_factory()

        endpoint_id = endpoint_factory(
            project_id,
            url=endpoint_url,
        )

        subscription_factory(
            endpoint_id,
            event_type,
        )

        event_id = event_factory(
            project_id,
            event_type,
        )

        response = client.get(f"/events/{event_id}/deliveries")

        assert response.status_code == 200

        deliveries = response.json()
        assert len(deliveries) == 1

        return deliveries[0]["id"]

    return create_delivery


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as client:
        yield client
