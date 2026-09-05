from uuid import uuid4


def test_create_project(client):
    response = client.post(
        "/projects",
        json={
            "name": "Test Project",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Test Project"
    assert "id" in data
    assert "created_at" in data


def test_get_project(client):
    create_response = client.post(
        "/projects",
        json={
            "name": "Project For Get",
        },
    )

    project_id = create_response.json()["id"]

    response = client.get(f"/projects/{project_id}")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == project_id
    assert data["name"] == "Project For Get"


def test_get_nonexistent_project(client):
    project_id = uuid4()

    response = client.get(f"/projects/{project_id}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}


def test_list_projects(client, project_factory):
    project_id = project_factory()

    response = client.get("/projects", params={"limit": 100})

    assert response.status_code == 200
    assert project_id in {project["id"] for project in response.json()}
