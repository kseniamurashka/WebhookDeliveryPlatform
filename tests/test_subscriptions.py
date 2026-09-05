from uuid import uuid4


def test_create_subscription(client, project_factory, endpoint_factory):
    project_id = project_factory()
    endpoint_id = endpoint_factory(project_id)

    response = client.post(
        "/subscriptions", json={"endpoint_id": endpoint_id, "event_type": "payment.completed"}
    )

    assert response.status_code == 201

    data = response.json()

    assert data["endpoint_id"] == endpoint_id
    assert data["event_type"] == "payment.completed"
    assert "id" in data
    assert "created_at" in data


def test_create_subscription_for_nonexistent_endpoint(client):
    endpoint_id = uuid4()

    response = client.post(
        "/subscriptions", json={"endpoint_id": str(endpoint_id), "event_type": "payment.completed"}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Endpoint not found"}


def test_create_subscription_for_all_events(client, project_factory, endpoint_factory):
    project_id = project_factory()
    endpoint_id = endpoint_factory(project_id)

    response = client.post("/subscriptions", json={"endpoint_id": endpoint_id, "event_type": "*"})

    assert response.status_code == 201

    data = response.json()

    assert data["endpoint_id"] == endpoint_id
    assert data["event_type"] == "*"


def test_cannot_create_duplicate_subscription(client, project_factory, endpoint_factory):
    project_id = project_factory()
    endpoint_id = endpoint_factory(project_id)

    payload = {
        "endpoint_id": endpoint_id,
        "event_type": "payment.completed",
    }

    first_response = client.post(
        "/subscriptions",
        json=payload,
    )

    second_response = client.post(
        "/subscriptions",
        json=payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {"detail": "Subscription already exists"}


def test_subscription_can_be_deleted(client, project_factory, endpoint_factory):
    endpoint_id = endpoint_factory(project_factory())
    subscription = client.post(
        "/subscriptions",
        json={"endpoint_id": endpoint_id, "event_type": "order.deleted"},
    ).json()

    response = client.delete(f"/subscriptions/{subscription['id']}")
    remaining = client.get("/subscriptions", params={"endpoint_id": endpoint_id})

    assert response.status_code == 204
    assert remaining.json() == []
