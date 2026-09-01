"""Authentication and role-boundary integration tests."""

FEATURE = {
    "feature_type": "cto",
    "name": "CTO TESTE 01",
    "status": "planned",
    "geometry": {"type": "Point", "coordinates": [-46.6333, -23.5505]},
    "properties": {"capacity": 16},
}


def test_invalid_password_is_rejected(client):
    response = client.post(
        "/api/v1/auth/token",
        data={"username": "viewer_test", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_viewer_can_read_but_cannot_change_map(client, viewer_headers):
    assert client.get("/api/v1/map-features", headers=viewer_headers).status_code == 200
    assert (
        client.post("/api/v1/map-features", headers=viewer_headers, json=FEATURE).status_code == 403
    )


def test_admin_can_create_update_and_delete_map_feature(client, admin_headers, viewer_headers):
    created = client.post("/api/v1/map-features", headers=admin_headers, json=FEATURE)
    assert created.status_code == 201, created.text
    feature = created.json()
    feature_id = feature["id"]

    visible = client.get("/api/v1/map-features", headers=viewer_headers)
    assert visible.status_code == 200
    assert visible.json()["features"][0]["properties"]["name"] == "CTO TESTE 01"

    viewer_update = client.patch(
        f"/api/v1/map-features/{feature_id}",
        headers=viewer_headers,
        json={"name": "BLOQUEADO", "expected_revision": 1},
    )
    assert viewer_update.status_code == 403
    assert (
        client.delete(f"/api/v1/map-features/{feature_id}", headers=viewer_headers).status_code
        == 403
    )

    updated = client.patch(
        f"/api/v1/map-features/{feature_id}",
        headers=admin_headers,
        json={
            "name": "CABO TESTE 01 ATUALIZADO",
            "feature_type": "cable",
            "properties": {"fiber_count": 24},
            "expected_revision": 1,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["properties"]["revision"] == 2
    assert updated.json()["properties"]["feature_type"] == "cable"
    assert updated.json()["properties"]["fiber_count"] == 24
    assert updated.json()["properties"]["feature_type_override"] == "cable"

    stale = client.patch(
        f"/api/v1/map-features/{feature_id}",
        headers=admin_headers,
        json={"name": "CONFLITO", "expected_revision": 1},
    )
    assert stale.status_code == 409

    removed = client.delete(f"/api/v1/map-features/{feature_id}", headers=admin_headers)
    assert removed.status_code == 204


def test_only_admin_can_create_accounts(client, admin_headers, viewer_headers):
    payload = {
        "username": "novo_visualizador",
        "password": "a-secure-viewer-password",
        "role": "viewer",
    }
    denied = client.post("/api/v1/users", headers=viewer_headers, json=payload)
    assert denied.status_code == 403

    created = client.post("/api/v1/users", headers=admin_headers, json=payload)
    assert created.status_code == 201, created.text
    assert created.json()["role"] == "viewer"
    assert "password" not in created.json()

    assert client.get("/api/v1/users", headers=viewer_headers).status_code == 403
    assert client.get("/api/v1/users", headers=admin_headers).status_code == 200
