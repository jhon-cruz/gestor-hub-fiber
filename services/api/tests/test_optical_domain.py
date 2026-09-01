"""Optical device, generated port capacity and RBAC integration tests."""

POINT = {"type": "Point", "coordinates": [-46.6333, -23.5505]}


def create_map_feature(client, admin_headers, feature_type, name):
    response = client.post(
        "/api/v1/map-features",
        headers=admin_headers,
        json={
            "feature_type": feature_type,
            "name": name,
            "status": "active",
            "geometry": POINT,
            "properties": {},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_cto_capacity_generates_ports_and_enforces_rbac(client, admin_headers, viewer_headers):
    feature = create_map_feature(client, admin_headers, "cto", "CTO DOMÍNIO 01")
    payload = {
        "map_feature_id": feature["id"],
        "device_type": "cto",
        "name": "CTO DOMÍNIO 01",
        "status": "active",
        "manufacturer": "Fabricante teste",
        "model": "16 portas",
        "port_capacity": 16,
        "properties": {"installation": "aerial"},
    }

    denied = client.post("/api/v1/optical-devices", headers=viewer_headers, json=payload)
    assert denied.status_code == 403

    created = client.post("/api/v1/optical-devices", headers=admin_headers, json=payload)
    assert created.status_code == 201, created.text
    device = created.json()
    assert device["port_summary"] == {
        "total": 16,
        "available": 16,
        "reserved": 0,
        "occupied": 0,
        "damaged": 0,
        "deactivated": 0,
    }

    listed = client.get("/api/v1/optical-devices", headers=viewer_headers)
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "CTO DOMÍNIO 01"

    ports = client.get(f"/api/v1/optical-devices/{device['id']}/ports", headers=viewer_headers)
    assert ports.status_code == 200
    assert len(ports.json()) == 16
    assert {port["port_kind"] for port in ports.json()} == {"cto_distribution"}

    first_port = ports.json()[0]
    viewer_update = client.patch(
        f"/api/v1/optical-ports/{first_port['id']}",
        headers=viewer_headers,
        json={"status": "occupied", "expected_revision": 1},
    )
    assert viewer_update.status_code == 403
    occupied = client.patch(
        f"/api/v1/optical-ports/{first_port['id']}",
        headers=admin_headers,
        json={"status": "occupied", "label": "Cliente teste", "expected_revision": 1},
    )
    assert occupied.status_code == 200, occupied.text
    assert occupied.json()["revision"] == 2

    summary = client.get(f"/api/v1/optical-devices/{device['id']}", headers=viewer_headers)
    assert summary.json()["port_summary"]["occupied"] == 1
    assert summary.json()["port_summary"]["available"] == 15

    stale = client.patch(
        f"/api/v1/optical-ports/{first_port['id']}",
        headers=admin_headers,
        json={"status": "available", "expected_revision": 1},
    )
    assert stale.status_code == 409

    map_items = client.get("/api/v1/map-features", headers=viewer_headers).json()
    properties = map_items["features"][0]["properties"]
    assert properties["capacity"] == 16
    assert properties["optical_device_id"] == device["id"]


def test_splitter_has_explicit_input_outputs_and_unique_map_link(client, admin_headers):
    feature = create_map_feature(client, admin_headers, "splitter", "SPLITTER 1:8")
    payload = {
        "map_feature_id": feature["id"],
        "device_type": "splitter",
        "name": "SPLITTER 1:8",
        "status": "active",
        "port_capacity": 8,
    }
    created = client.post("/api/v1/optical-devices", headers=admin_headers, json=payload)
    assert created.status_code == 201, created.text
    device = created.json()
    assert device["port_summary"]["total"] == 9

    ports = client.get(
        f"/api/v1/optical-devices/{device['id']}/ports", headers=admin_headers
    ).json()
    assert len([port for port in ports if port["port_kind"] == "splitter_input"]) == 1
    assert len([port for port in ports if port["port_kind"] == "splitter_output"]) == 8

    duplicate = client.post("/api/v1/optical-devices", headers=admin_headers, json=payload)
    assert duplicate.status_code == 409

    mismatch = client.post(
        "/api/v1/optical-devices",
        headers=admin_headers,
        json={**payload, "device_type": "olt", "name": "OLT incompatível"},
    )
    assert mismatch.status_code == 422
