from uuid import uuid4


def test_create_event(client, project_factory):
    project_id = project_factory()
    response = client.post(
        "/events",
        json={
            "project_id": project_id,
            "event_type": "test.create.event",
            "payload": {
                "hello": "world",
            },
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["project_id"] == project_id
    assert data["event_type"] == "test.create.event"
    assert "hello" in data["payload"]
    assert data["payload"]["hello"] == "world"
    assert "id" in data
    assert "created_at" in data


def test_create_event_for_nonexistent_project(client):
    project_id = uuid4()

    response = client.post(
        "/events",
        json={
            "project_id": str(project_id),
            "event_type": "test.create.event",
            "payload": {
                "hello": "world",
            },
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def test_event_creation_is_idempotent(client, project_factory):
    project_id = project_factory()
    payload = {
        "project_id": project_id,
        "event_type": "payment.completed",
        "payload": {"payment_id": 42},
    }
    headers = {"Idempotency-Key": "payment-42-completed"}

    first = client.post("/events", json=payload, headers=headers)
    second = client.post("/events", json=payload, headers=headers)

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert second.json()["idempotency_key"] == "payment-42-completed"


def test_list_events_can_be_filtered_by_project(client, project_factory, event_factory):
    first_project_id = project_factory()
    second_project_id = project_factory()
    event_factory(first_project_id, event_type="order.created")
    event_factory(second_project_id, event_type="order.created")

    response = client.get("/events", params={"project_id": first_project_id})

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["project_id"] == first_project_id
