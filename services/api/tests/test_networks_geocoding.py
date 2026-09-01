"""Named network navigation and cached address search tests."""

from app.core.database import SessionLocal
from app.models.map_feature import MapFeature


def test_network_groups_existing_source_and_filters_map(client, admin_headers, viewer_headers):
    feature = client.post(
        "/api/v1/map-features",
        headers=admin_headers,
        json={
            "feature_type": "cable",
            "name": "CABO PRAIA GRANDE",
            "status": "active",
            "geometry": {
                "type": "LineString",
                "coordinates": [[-46.43, -24.01], [-46.42, -24.02]],
            },
            "properties": {"fiber_count": 24},
        },
    )
    assert feature.status_code == 201, feature.text
    with SessionLocal.begin() as db:
        item = db.get(MapFeature, feature.json()["id"])
        item.source_namespace = "rede-praia-grande"
        item.source_ref = "cabo-1"

    payload = {
        "name": "Praia Grande",
        "city": "Praia Grande",
        "state": "São Paulo",
        "source_namespace": "rede-praia-grande",
    }
    denied = client.post("/api/v1/networks", headers=viewer_headers, json=payload)
    assert denied.status_code == 403

    created = client.post("/api/v1/networks", headers=admin_headers, json=payload)
    assert created.status_code == 201, created.text
    network = created.json()
    assert network["feature_count"] == 1
    assert network["viewport"] == [-46.43, -24.02, -46.42, -24.01]

    listed = client.get("/api/v1/networks", headers=viewer_headers)
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "Praia Grande"

    filtered = client.get(
        f"/api/v1/map-features?network_id={network['id']}", headers=viewer_headers
    )
    assert len(filtered.json()["features"]) == 1
    assert filtered.json()["data_status"]["latest_feature_update_at"] is not None
    assert filtered.json()["data_status"]["base_map"].startswith("OpenStreetMap")
    assert filtered.json()["features"][0]["properties"]["network_id"] == network["id"]

    duplicate = client.post("/api/v1/networks", headers=admin_headers, json=payload)
    assert duplicate.status_code == 409

    niteroi = client.post(
        "/api/v1/networks",
        headers=admin_headers,
        json={
            "name": "Niterói",
            "city": "Niterói",
            "state": "Rio de Janeiro",
            "viewport": [-43.14, -22.95, -43.02, -22.84],
        },
    )
    assert niteroi.status_code == 201, niteroi.text
    assert niteroi.json()["feature_count"] == 0


def test_address_search_is_authenticated_cached_and_network_biased(
    client, admin_headers, viewer_headers, monkeypatch
):
    calls = 0

    network = client.post(
        "/api/v1/networks",
        headers=admin_headers,
        json={
            "name": "Praia Grande",
            "city": "Praia Grande",
            "state": "São Paulo",
            "viewport": [-46.53, -24.1, -46.35, -23.95],
        },
    ).json()

    async def fake_search(query, limit, viewport):
        nonlocal calls
        calls += 1
        assert query == "Rua Fumio Miyazi, Praia Grande, São Paulo"
        assert limit == 5
        assert viewport == [-46.53, -24.1, -46.35, -23.95]
        return [
            {
                "label": "Rua Fumio Miyazi, Praia Grande, São Paulo, Brasil",
                "latitude": -24.007,
                "longitude": -46.425,
                "viewport": [-46.43, -24.01, -46.42, -24.0],
                "category": "highway",
                "type": "residential",
            }
        ]

    monkeypatch.setattr("app.api.routes.geocoding.search_addresses", fake_search)
    path = f"/api/v1/geocoding/search?q=Rua%20Fumio%20Miyazi&network_id={network['id']}"
    assert client.get(path).status_code == 401

    first = client.get(path, headers=viewer_headers)
    assert first.status_code == 200, first.text
    assert first.json()["cached"] is False
    assert first.json()["network_bias"] is True
    assert first.json()["results"][0]["longitude"] == -46.425

    second = client.get(path, headers=viewer_headers)
    assert second.status_code == 200
    assert second.json()["cached"] is True
    assert calls == 1
