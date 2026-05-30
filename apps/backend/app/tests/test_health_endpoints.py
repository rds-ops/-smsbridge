from __future__ import annotations

import pytest

import app.main as main


def test_health_live_ok(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ready_ok(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"


def test_health_ready_db_failure_returns_503(client, monkeypatch):
    class _FailingEngine:
        def connect(self):
            raise RuntimeError("db down")

    monkeypatch.setattr(main, "engine", _FailingEngine())
    response = client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["database"] == "error"

