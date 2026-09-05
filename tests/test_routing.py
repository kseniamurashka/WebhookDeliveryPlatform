def get_event_deliveries(client, event_id):
    response = client.get(f"/events/{event_id}/deliveries")
    assert response.status_code == 200

    return response.json()


def test_event_creates_delivery_for_subscribed_endpoint(
    client,
    project_factory,
    endpoint_factory,
    subscription_factory,
    event_factory,
):
    project_id = project_factory()
    endpoint_id = endpoint_factory(project_id)

    subscription_factory(
        endpoint_id,
        "payment.completed",
    )

    event_id = event_factory(
        project_id,
        "payment.completed",
    )

    deliveries = get_event_deliveries(client, event_id)

    assert len(deliveries) == 1
    assert deliveries[0]["endpoint_id"] == endpoint_id


def test_event_does_not_create_delivery_for_unsubscribed_endpoint(
    client,
    project_factory,
    endpoint_factory,
    subscription_factory,
    event_factory,
):
    project_id = project_factory()
    subscribed_endpoint_id = endpoint_factory(project_id)
    unsubscribed_endpoint_id = endpoint_factory(project_id)

    subscription_factory(
        subscribed_endpoint_id,
        "payment.created",
    )
    subscription_factory(
        unsubscribed_endpoint_id,
        "payment.completed",
    )

    event_id = event_factory(project_id, "payment.created")

    deliveries = get_event_deliveries(client, event_id)

    assert len(deliveries) == 1

    endpoint_ids = [delivery["endpoint_id"] for delivery in deliveries]

    assert subscribed_endpoint_id in endpoint_ids
    assert unsubscribed_endpoint_id not in endpoint_ids


def test_event_routes_only_to_endpoints_of_its_project(
    client,
    project_factory,
    endpoint_factory,
    subscription_factory,
    event_factory,
):
    project_a = project_factory()
    project_b = project_factory()

    endpoint_a = endpoint_factory(project_a)
    endpoint_b = endpoint_factory(project_b)

    event_type = "union.event.type"

    subscription_factory(
        endpoint_a,
        event_type,
    )
    subscription_factory(
        endpoint_b,
        event_type,
    )

    event_id = event_factory(
        project_a,
        event_type,
    )

    deliveries = get_event_deliveries(client, event_id)

    assert len(deliveries) == 1
    assert deliveries[0]["endpoint_id"] == endpoint_a

    endpoint_ids = [delivery["endpoint_id"] for delivery in deliveries]
    assert endpoint_b not in endpoint_ids


def test_wildcard_subscription_receives_all_events(
    client,
    project_factory,
    endpoint_factory,
    subscription_factory,
    event_factory,
):
    project_id = project_factory()
    endpoint_id = endpoint_factory(project_id)

    subscription_factory(endpoint_id, "*")

    event_a = event_factory(project_id, "event.type.1")
    event_b = event_factory(project_id, "event.type.2")

    deliveries_a = get_event_deliveries(client, event_a)
    assert len(deliveries_a) == 1
    assert deliveries_a[0]["endpoint_id"] == endpoint_id

    deliveries_b = get_event_deliveries(client, event_b)
    assert len(deliveries_b) == 1
    assert deliveries_b[0]["endpoint_id"] == endpoint_id


def test_exact_and_wildcard_subscription_create_only_one_delivery(
    client,
    project_factory,
    endpoint_factory,
    subscription_factory,
    event_factory,
):
    project_id = project_factory()
    endpoint_id = endpoint_factory(project_id)

    subscription_factory(endpoint_id, "*")
    subscription_factory(
        endpoint_id,
        "exact.event",
    )

    event_id = event_factory(
        project_id,
        "exact.event",
    )

    deliveries = get_event_deliveries(client, event_id)
    assert len(deliveries) == 1
    assert deliveries[0]["endpoint_id"] == endpoint_id


def test_delivery_for_inactive_endpoint_does_not_create(
    client,
    project_factory,
    endpoint_factory,
    subscription_factory,
    event_factory,
):
    project_id = project_factory()
    endpoint_id = endpoint_factory(project_id)

    subscription_factory(
        endpoint_id,
        "payment.for.inactave.endpoint",
    )

    response = client.patch(
        f"/endpoints/{endpoint_id}/deactivate",
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False

    event_id = event_factory(
        project_id,
        "payment.for.inactave.endpoint",
    )

    deliveries = get_event_deliveries(client, event_id)

    assert len(deliveries) == 0
