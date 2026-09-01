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


def test_fiber_port_links_trace_and_optical_budget(client, admin_headers, viewer_headers):
    line_a = {"type": "LineString", "coordinates": [[-46.43, -24.01], [-46.42, -24.02]]}
    line_b = {"type": "LineString", "coordinates": [[-46.42, -24.02], [-46.41, -24.03]]}
    feature_a = create_feature(client, admin_headers, "cable", "FEEDER A", line_a)
    feature_b = create_feature(client, admin_headers, "cable", "DISTRIBUIÇÃO B", line_b)
    enclosure = create_feature(
        client,
        admin_headers,
        "splice_box",
        "CE TRAÇO 01",
        {"type": "Point", "coordinates": [-46.42, -24.02]},
    )

    def structured_cable(feature, name, length):
        response = client.post(
            "/api/v1/optical-cables",
            headers=admin_headers,
            json={
                "map_feature_id": feature["id"],
                "name": name,
                "cable_class": "distribution",
                "status": "active",
                "fiber_count": 12,
                "tube_count": 1,
                "fibers_per_tube": 12,
                "measured_length_m": length,
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    cable_a = structured_cable(feature_a, "FEEDER A", 1000)
    cable_b = structured_cable(feature_b, "DISTRIBUIÇÃO B", 2000)
    fiber_a = client.get(
        f"/api/v1/optical-cables/{cable_a['id']}/fibers", headers=admin_headers
    ).json()[0]
    fiber_b = client.get(
        f"/api/v1/optical-cables/{cable_b['id']}/fibers", headers=admin_headers
    ).json()[0]

    def device(name, device_type):
        response = client.post(
            "/api/v1/optical-devices",
            headers=admin_headers,
            json={
                "device_type": device_type,
                "name": name,
                "status": "active",
                "port_capacity": 1,
            },
        )
        assert response.status_code == 201, response.text
        item = response.json()
        port = client.get(
            f"/api/v1/optical-devices/{item['id']}/ports", headers=admin_headers
        ).json()[0]
        return item, port

    _, olt_port = device("OLT TESTE", "olt")
    _, cto_port = device("CTO TESTE", "cto")
    source_link = {
        "fiber_id": fiber_a["id"],
        "fiber_end": "a",
        "port_id": olt_port["id"],
        "insertion_loss_db": 0.2,
    }
    assert (
        client.post(
            "/api/v1/fiber-port-links", headers=viewer_headers, json=source_link
        ).status_code
        == 403
    )
    linked_source = client.post("/api/v1/fiber-port-links", headers=admin_headers, json=source_link)
    assert linked_source.status_code == 201, linked_source.text
    links = client.get(f"/api/v1/fiber-port-links?port_id={olt_port['id']}", headers=viewer_headers)
    assert links.status_code == 200
    assert links.json()[0]["fiber"]["global_position"] == 1
    occupied_port = client.get(
        f"/api/v1/optical-devices/{links.json()[0]['port']['device_id']}/ports",
        headers=admin_headers,
    ).json()[0]
    cannot_free_connected_port = client.patch(
        f"/api/v1/optical-ports/{olt_port['id']}",
        headers=admin_headers,
        json={"status": "available", "expected_revision": occupied_port["revision"]},
    )
    assert cannot_free_connected_port.status_code == 409
    fusion = client.post(
        "/api/v1/fiber-connections",
        headers=admin_headers,
        json={
            "enclosure_feature_id": enclosure["id"],
            "loss_db": 0.1,
            "endpoints": [
                {"fiber_id": fiber_a["id"], "end_side": "b"},
                {"fiber_id": fiber_b["id"], "end_side": "a"},
            ],
        },
    )
    assert fusion.status_code == 201, fusion.text
    target_link = client.post(
        "/api/v1/fiber-port-links",
        headers=admin_headers,
        json={
            "fiber_id": fiber_b["id"],
            "fiber_end": "b",
            "port_id": cto_port["id"],
            "insertion_loss_db": 0.2,
        },
    )
    assert target_link.status_code == 201, target_link.text

    trace = client.get(f"/api/v1/optical-traces/from-port/{olt_port['id']}", headers=viewer_headers)
    assert trace.status_code == 200, trace.text
    assert trace.json()["complete"] is True
    assert trace.json()["paths"][0]["destination"].startswith("CTO TESTE")
    assert trace.json()["paths"][0]["complete"] is True
    assert trace.json()["paths"][0]["total_loss_db"] == 1.55
    assert trace.json()["paths"][0]["length_m"] == 3000
    assert trace.json()["paths"][0]["margin_db"] == 28.45

    endpoint_conflict = client.post(
        "/api/v1/fiber-connections",
        headers=admin_headers,
        json={
            "enclosure_feature_id": enclosure["id"],
            "endpoints": [
                {"fiber_id": fiber_a["id"], "end_side": "a"},
                {"fiber_id": fiber_b["id"], "end_side": "b"},
            ],
        },
    )
    assert endpoint_conflict.status_code == 409
