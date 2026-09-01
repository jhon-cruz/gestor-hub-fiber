"""Cable generation, fiber state and endpoint integrity tests."""


def create_feature(client, headers, feature_type, name, geometry):
    response = client.post(
        "/api/v1/map-features",
        headers=headers,
        json={
            "feature_type": feature_type,
            "name": name,
            "status": "active",
            "geometry": geometry,
            "properties": {},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_cable(client, headers, feature_id, name):
    response = client.post(
        "/api/v1/optical-cables",
        headers=headers,
        json={
            "map_feature_id": feature_id,
            "name": name,
            "cable_class": "distribution",
            "status": "active",
            "fiber_count": 24,
            "tube_count": 2,
            "fibers_per_tube": 12,
            "technical_reserve_m": 20,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_cable_generates_tubes_and_individual_fibers(client, admin_headers, viewer_headers):
    line = {"type": "LineString", "coordinates": [[-46.43, -24.01], [-46.42, -24.02]]}
    feature = create_feature(client, admin_headers, "cable", "CABO 24FO", line)
    payload = {
        "map_feature_id": feature["id"],
        "name": "CABO 24FO",
        "cable_class": "distribution",
        "fiber_count": 24,
        "tube_count": 2,
        "fibers_per_tube": 12,
    }
    assert (
        client.post("/api/v1/optical-cables", headers=viewer_headers, json=payload).status_code
        == 403
    )
    cable = client.post("/api/v1/optical-cables", headers=admin_headers, json=payload)
    assert cable.status_code == 201, cable.text
    assert cable.json()["fiber_summary"]["available"] == 24

    fibers = client.get(
        f"/api/v1/optical-cables/{cable.json()['id']}/fibers", headers=viewer_headers
    )
    assert fibers.status_code == 200
    assert len(fibers.json()) == 24
    assert fibers.json()[0]["tube_position"] == 1
    assert fibers.json()[11]["position"] == 12
    assert fibers.json()[12]["tube_position"] == 2
    assert fibers.json()[12]["position"] == 1

    first = fibers.json()[0]
    denied = client.patch(
        f"/api/v1/optical-fibers/{first['id']}",
        headers=viewer_headers,
        json={"status": "occupied", "expected_revision": 1},
    )
    assert denied.status_code == 403
    updated = client.patch(
        f"/api/v1/optical-fibers/{first['id']}",
        headers=admin_headers,
        json={"status": "occupied", "expected_revision": 1},
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2

    duplicate = client.post("/api/v1/optical-cables", headers=admin_headers, json=payload)
    assert duplicate.status_code == 409

    invalid_capacity = client.post(
        "/api/v1/optical-cables",
        headers=admin_headers,
        json={**payload, "map_feature_id": None, "fiber_count": 25},
    )
    assert invalid_capacity.status_code == 422


def test_splice_uses_each_fiber_endpoint_only_once(client, admin_headers, viewer_headers):
    line_a = {"type": "LineString", "coordinates": [[-46.43, -24.01], [-46.42, -24.02]]}
    line_b = {"type": "LineString", "coordinates": [[-46.42, -24.02], [-46.41, -24.03]]}
    cable_a_feature = create_feature(client, admin_headers, "cable", "CABO A", line_a)
    cable_b_feature = create_feature(client, admin_headers, "cable", "CABO B", line_b)
    enclosure = create_feature(
        client,
        admin_headers,
        "splice_box",
        "CE 01",
        {"type": "Point", "coordinates": [-46.42, -24.02]},
    )
    cable_a = create_cable(client, admin_headers, cable_a_feature["id"], "CABO A")
    cable_b = create_cable(client, admin_headers, cable_b_feature["id"], "CABO B")
    fiber_a = client.get(
        f"/api/v1/optical-cables/{cable_a['id']}/fibers", headers=admin_headers
    ).json()[0]
    fiber_b = client.get(
        f"/api/v1/optical-cables/{cable_b['id']}/fibers", headers=admin_headers
    ).json()[0]
    payload = {
        "enclosure_feature_id": enclosure["id"],
        "connection_type": "fusion",
        "loss_db": 0.1,
        "endpoints": [
            {"fiber_id": fiber_a["id"], "end_side": "b"},
            {"fiber_id": fiber_b["id"], "end_side": "a"},
        ],
    }
    assert (
        client.post("/api/v1/fiber-connections", headers=viewer_headers, json=payload).status_code
        == 403
    )
    created = client.post("/api/v1/fiber-connections", headers=admin_headers, json=payload)
    assert created.status_code == 201, created.text
    assert len(created.json()["endpoints"]) == 2
    refreshed = client.get(
        f"/api/v1/optical-cables/{cable_a['id']}/fibers", headers=viewer_headers
    ).json()[0]
    assert refreshed["connected_ends"] == ["b"]

    conflict = client.post("/api/v1/fiber-connections", headers=admin_headers, json=payload)
    assert conflict.status_code == 409
    listed = client.get(
        f"/api/v1/fiber-connections?enclosure_feature_id={enclosure['id']}",
        headers=viewer_headers,
    )
    assert len(listed.json()) == 1

    removed = client.delete(
        f"/api/v1/fiber-connections/{created.json()['id']}", headers=admin_headers
    )
    assert removed.status_code == 204
    recreated = client.post("/api/v1/fiber-connections", headers=admin_headers, json=payload)
    assert recreated.status_code == 201
