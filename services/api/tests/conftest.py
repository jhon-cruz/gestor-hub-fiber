"""PostGIS-backed API integration fixtures."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.engine import make_url

from app.core.config import get_settings
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


def _require_isolated_test_database() -> None:
    """Abort before destructive fixtures can touch a non-test database."""

    settings = get_settings()
    database_name = make_url(settings.database_url).database or ""
    if settings.environment != "test" or not database_name.endswith("_test"):
        pytest.fail(
            "Refusing to run destructive tests outside an isolated *_test database "
            "with APP_ENVIRONMENT=test. Use `make test`.",
            pytrace=False,
        )


@pytest.fixture(scope="session", autouse=True)
def require_isolated_test_database():
    _require_isolated_test_database()


@pytest.fixture(autouse=True)
def clean_database():
    _require_isolated_test_database()
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
