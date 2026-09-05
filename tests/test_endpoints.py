from uuid import uuid4


def test_create_endpoint(client, project_factory):
    project_id = project_factory()
    response = client.post(
        "/endpoints",
        json={
            "project_id": project_id,
            "url": "https://example.com/webhooks",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["project_id"] == project_id
    assert data["url"] == "https://example.com/webhooks"
    assert data["is_active"] is True

    assert "id" in data
    assert "created_at" in data
    assert "secret" in data


def test_get_endpoint(client, project_factory):
    project_id = project_factory()
    response = client.post(
        "/endpoints",
        json={
            "project_id": project_id,
            "url": "https://example.com/webhooks",
        },
    )

    endpoint_id = response.json()["id"]

    response = client.get(
        f"/endpoints/{endpoint_id}",
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == endpoint_id
    assert data["project_id"] == project_id

    assert "secret" not in data


def test_create_endpoint_for_nonexistent_project(client):
    project_id = uuid4()

    response = client.post(
        "/endpoints",
        json={
            "project_id": str(project_id),
            "url": "https://example.com/webhooks",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def test_get_nonexistent_endpoint(client):
    endpoint_id = uuid4()

    response = client.get(
        f"/endpoints/{endpoint_id}",
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Endpoint not found"}


def test_endpoint_can_be_reactivated(client, project_factory, endpoint_factory):
    endpoint_id = endpoint_factory(project_factory())
    client.patch(f"/endpoints/{endpoint_id}/deactivate")

    response = client.patch(f"/endpoints/{endpoint_id}/activate")

    assert response.status_code == 200
    assert response.json()["is_active"] is True


def test_endpoint_secret_can_be_rotated(client, project_factory):
    created = client.post(
        "/endpoints",
        json={
            "project_id": project_factory(),
            "url": "https://example.com/webhooks",
        },
    ).json()

    response = client.post(f"/endpoints/{created['id']}/rotate-secret")

    assert response.status_code == 200
    assert response.json()["secret"] != created["secret"]
