"""Every API route needs a token, except health and login (M.1). No database."""
from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app
from app.services import auth

OPEN = {("GET", "/api/health"), ("POST", "/api/auth/login"), ("GET", "/")}
ADMIN_ONLY = {
    ("DELETE", "/api/connectors/{connector_id}"),
    ("POST", "/api/documents/ingest-path"),
    ("GET", "/api/admin/users"),
    ("POST", "/api/admin/users"),
    ("PATCH", "/api/admin/users/{user_id}"),
    ("GET", "/api/admin/terminology"),
    ("PUT", "/api/admin/terminology"),
    ("DELETE", "/api/admin/terminology/{term}"),
}


def _routes():
    for r in app.routes:
        if isinstance(r, APIRoute):
            for m in r.methods - {"HEAD", "OPTIONS"}:
                if (m, r.path) not in OPEN:
                    yield m, r.path


@pytest.fixture(scope="module")
def client():
    # No lifespan: routes must reject before touching the database.
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setenv("AUTH_SECRET", "test-secret")


def _url(path: str) -> str:
    return path.replace("{log_id}", "1").replace("{connector_id}", "1").replace("{user_id}", "1").replace("{term}", "x").replace(
        "{job_id}", "x").replace("{item_id}", "1").replace("{run_id}", "1").replace(
        "{unified_id}", "x")


def test_routes_found():
    assert len(list(_routes())) > 20


@pytest.mark.parametrize("method,path", sorted(_routes()))
def test_401_without_token(client, method, path):
    assert client.request(method, _url(path)).status_code == 401
    bad = client.request(method, _url(path), headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401


@pytest.mark.parametrize("method,path", sorted(ADMIN_ONLY))
@pytest.mark.parametrize("role", ["engineer", "manager"])
def test_admin_routes_403_for_other_roles(client, method, path, role):
    h = {"Authorization": f"Bearer {auth.make_token(1, role)}"}
    assert client.request(method, _url(path), headers=h).status_code == 403
