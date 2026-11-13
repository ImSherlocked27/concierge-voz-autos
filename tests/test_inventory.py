from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient

from inventory.app import ARGENTINA, CATALOG, app


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("TOOLS_SECRET", "local-test-only")
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("DEMO_ACCESS_CODE", "local-demo-only")
    with TestClient(app) as instance:
        yield instance


@pytest.fixture
def auth():
    return {"X-Tools-Secret": "local-test-only"}


def future_slot():
    value = (datetime.now(ARGENTINA) + timedelta(days=3)).replace(hour=10, minute=30, second=0, microsecond=0)
    while value.weekday() > 4:
        value += timedelta(days=1)
    return value


def payload(**kwargs):
    return {"vehicle_id": "auto-02", "starts_at": future_slot().isoformat(), "confirmed": True, "request_id": "request-0001", **kwargs}


def test_public_demo_loads_without_key(client):
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/health").json()["fictional"] is True
    assert len(client.get("/api/catalog").json()["vehicles"]) == 10


@pytest.mark.parametrize("path", ["/vehicles", "/vehicles/auto-01"])
def test_tools_require_secret(client, path):
    assert client.get(path).status_code == 401


def test_unconfigured_auth_fails_closed(client, monkeypatch):
    monkeypatch.delenv("TOOLS_SECRET")
    assert client.get("/vehicles").status_code == 503


def test_suv_grounded_filters(client, auth):
    result = client.get("/vehicles", params={"max_price": 22000, "body": "suv", "feature": "isofix"}, headers=auth).json()
    assert result["total"] == 3
    assert [vehicle["id"] for vehicle in result["vehicles"]] == ["auto-03", "auto-07", "auto-02"]
    assert all(vehicle in CATALOG for vehicle in result["vehicles"])
    assert all(vehicle["price_usd"] <= 22000 for vehicle in result["vehicles"])


def test_zero_results_does_not_relax_budget(client, auth):
    assert client.get("/vehicles", params={"max_price": 100}, headers=auth).json()["vehicles"] == []


@pytest.mark.parametrize("params", [{"max_price": -1}, {"max_price": "NaN"}, {"max_price": "Infinity"}, {"limit": 99}, {"body": "spaceship"}])
def test_invalid_filters_rejected(client, auth, params):
    assert client.get("/vehicles", params=params, headers=auth).status_code == 422


def test_missing_vehicle_is_404(client, auth):
    assert client.get("/vehicles/invented", headers=auth).status_code == 404
    assert client.post("/visits", json=payload(vehicle_id="invented"), headers=auth).status_code == 404


def test_visit_requires_auth_and_confirmation(client, auth):
    assert client.post("/visits", json=payload()).status_code == 401
    assert client.post("/visits", json=payload(confirmed=False), headers=auth).status_code == 422


def test_visit_is_idempotent_and_slot_conflicts(client, auth):
    first = client.post("/visits", json=payload(), headers=auth)
    assert first.status_code == 200
    assert first.json()["status"] == "confirmed_mock"
    assert client.post("/visits", json=payload(), headers=auth).json()["visit_id"] == first.json()["visit_id"]
    assert client.post("/visits", json=payload(request_id="another-request"), headers=auth).status_code == 409
    assert client.post("/visits", json=payload(vehicle_id="auto-03"), headers=auth).status_code == 409


@pytest.mark.parametrize("date", [lambda: datetime.now(ARGENTINA) - timedelta(days=1), lambda: datetime.now(ARGENTINA) + timedelta(days=40), lambda: future_slot().replace(hour=19), lambda: future_slot().replace(minute=17)])
def test_invalid_visit_time(client, auth, date):
    assert client.post("/visits", json=payload(starts_at=date().isoformat()), headers=auth).status_code == 422


def test_visit_requires_timezone_and_rejects_personal_fields(client, auth):
    assert client.post("/visits", json=payload(starts_at="2027-01-01T10:30:00"), headers=auth).status_code == 422
    assert client.post("/visits", json=payload(email="someone@example.invalid"), headers=auth).status_code == 422


def test_concurrent_booking_only_one_succeeds(client, auth):
    def book(index):
        return client.post("/visits", json=payload(request_id=f"concurrent-{index}"), headers=auth).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(book, range(2))) == [200, 409]


def mock_voice(monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-only-not-a-real-key")
    monkeypatch.setenv("AGENT_ID", "test-agent")
    monkeypatch.setenv("DEMO_DAILY_SESSIONS", "1")
    monkeypatch.setattr("inventory.app.httpx.get", lambda *args, **kwargs: httpx.Response(200, json={"signed_url": "wss://example.invalid/session"}, request=httpx.Request("GET", "https://example.invalid")))


def test_voice_access_and_quota(client, monkeypatch):
    mock_voice(monkeypatch)
    assert client.post("/api/session", json={"access_code": "wrong"}).status_code == 401
    assert client.post("/api/session", json={"access_code": "local-demo-only"}).status_code == 200
    assert client.post("/api/session", json={"access_code": "local-demo-only"}).status_code == 429


def test_concurrent_session_quota(client, monkeypatch):
    mock_voice(monkeypatch)
    def start(_):
        return client.post("/api/session", json={"access_code": "local-demo-only"}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(start, range(2))) == [200, 429]


def test_voice_error_never_leaks_key(client, monkeypatch):
    mock_voice(monkeypatch)
    monkeypatch.setattr("inventory.app.httpx.get", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("private error details")))
    result = client.post("/api/session", json={"access_code": "local-demo-only"})
    assert result.status_code == 502
    assert "private error" not in result.text
    assert "test-only" not in result.text
