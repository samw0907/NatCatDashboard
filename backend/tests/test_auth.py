# backend/tests/test_auth.py

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import events, ingest, prune

GOOD_TOKEN = "t" * 40


@pytest.fixture
def client(db):
    def override():
        yield db

    for router_module in (events, ingest, prune):
        app.dependency_overrides[router_module.get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


WRITE_ENDPOINTS = [
    "/api/prune",
    "/api/ingest/usgs",
    "/api/ingest/nifc",
    "/api/ingest/nhc",
    "/api/ingest/gdacs",
]


@pytest.mark.parametrize("path", WRITE_ENDPOINTS)
def test_write_endpoints_disabled_when_no_token_configured(client, admin_token, path):
    admin_token("")
    resp = client.post(path, headers={"X-Admin-Token": "anything"})
    assert resp.status_code == 503


@pytest.mark.parametrize("path", WRITE_ENDPOINTS)
def test_write_endpoints_reject_missing_or_wrong_token(client, admin_token, path):
    admin_token(GOOD_TOKEN)
    assert client.post(path).status_code == 401
    assert client.post(path, headers={"X-Admin-Token": "wrong" * 10}).status_code == 401


def test_short_configured_token_counts_as_not_configured(client, admin_token):
    admin_token("short-token")
    resp = client.post("/api/prune", headers={"X-Admin-Token": "short-token"})
    assert resp.status_code == 503


def test_correct_token_allows_write_endpoint(client, admin_token):
    admin_token(GOOD_TOKEN)
    resp = client.post("/api/prune", headers={"X-Admin-Token": GOOD_TOKEN})
    assert resp.status_code == 200
    assert resp.json()["dry_run"] is True


def test_read_endpoints_stay_public(client, admin_token):
    admin_token(GOOD_TOKEN)
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/api/events").status_code == 200


def test_browser_cannot_preflight_a_post(client):
    resp = client.options(
        "/api/prune",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert resp.status_code == 400
