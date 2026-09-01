"""PostGIS-backed API integration fixtures."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.database import SessionLocal
from app.main import app
from app.models.audit import AuditLog
from app.models.fiber_topology import (
    CableTube,
    FiberConnection,
    FiberConnectionEndpoint,
    FiberPortLink,
    OpticalCable,
    OpticalFiber,
)
from app.models.geocode import GeocodeCache
from app.models.map_feature import MapFeature
from app.models.map_import import MapImport
from app.models.network import ServiceNetwork
from app.models.optical import OpticalDevice, OpticalPort
from app.models.user import User, UserRole
from app.services.security import hash_password


@pytest.fixture(autouse=True)
def clean_database():
    with SessionLocal.begin() as db:
        db.execute(delete(AuditLog))
        db.execute(delete(GeocodeCache))
        db.execute(delete(FiberPortLink))
        db.execute(delete(FiberConnectionEndpoint))
        db.execute(delete(FiberConnection))
        db.execute(delete(OpticalFiber))
        db.execute(delete(CableTube))
        db.execute(delete(OpticalCable))
        db.execute(delete(OpticalPort))
        db.execute(delete(OpticalDevice))
        db.execute(delete(MapFeature))
        db.execute(delete(MapImport))
        db.execute(delete(ServiceNetwork))
        db.execute(delete(User))
        db.add_all(
            [
                User(
                    username="admin_test",
                    password_hash=hash_password("correct-admin-password"),
                    role=UserRole.ADMIN,
                ),
                User(
                    username="viewer_test",
                    password_hash=hash_password("correct-viewer-password"),
                    role=UserRole.VIEWER,
                ),
            ]
        )
    yield


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/token", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
def admin_headers(client: TestClient) -> dict[str, str]:
    token = _login(client, "admin_test", "correct-admin-password")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def viewer_headers(client: TestClient) -> dict[str, str]:
    token = _login(client, "viewer_test", "correct-viewer-password")
    return {"Authorization": f"Bearer {token}"}
