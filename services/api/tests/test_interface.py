"""Initial graphical interface and safe bootstrap tests."""

from sqlalchemy import delete

from app.core.database import SessionLocal
from app.models.user import User


def test_interface_is_served_with_security_headers(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Gestor Hub Fiber" in response.text
    assert 'id="login-form"' in response.text
    assert 'id="map"' in response.text
    assert 'id="imports-dialog"' in response.text
    assert 'id="kmz-file"' in response.text
    assert 'id="theme-toggle"' in response.text
    assert 'id="map-theme-toggle"' not in response.text
    assert 'id="network-select"' in response.text
    assert 'id="network-dialog"' in response.text
    assert 'id="address-search-form"' in response.text
    assert 'id="detail-fiber-count"' in response.text
    assert 'id="inventory-view"' in response.text
    assert 'id="inventory-table-body"' in response.text
    assert 'id="optical-view"' in response.text
    assert 'id="device-create-dialog"' in response.text
    assert 'id="device-detail-dialog"' in response.text
    assert 'id="device-ports-list"' in response.text
    assert response.headers["x-frame-options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]

    assert client.get("/static/app.css").status_code == 200
    assert client.get("/static/app.js").status_code == 200


def test_bootstrap_creates_only_the_first_administrator(client):
    with SessionLocal.begin() as db:
        db.execute(delete(User))

    status = client.get("/api/v1/auth/bootstrap-status")
    assert status.status_code == 200
    assert status.json() == {"setup_required": True}

    created = client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "primeiro_admin", "password": "uma-senha-inicial-segura"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["token_type"] == "bearer"

    token = created.json()["access_token"]
    profile = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200
    assert profile.json()["role"] == "admin"

    repeated = client.post(
        "/api/v1/auth/bootstrap",
        json={"username": "segundo_admin", "password": "outra-senha-inicial-segura"},
    )
    assert repeated.status_code == 409
    assert client.get("/api/v1/auth/bootstrap-status").json() == {"setup_required": False}
