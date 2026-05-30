from __future__ import annotations
import os
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite:///./test_smsbridge.db"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ENVIRONMENT"] = "test"
os.environ["MOCK_SMS_DELAY_SECONDS"] = "0"
os.environ["MOCK_SUCCESS_RATE"] = "1"
os.environ["MOCK_ORDER_TIMEOUT_SECONDS"] = "1"
os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"

import pytest
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.seed import seed
from app.db.session import SessionLocal, engine
from app.main import app


@pytest.fixture(autouse=True)
def reset_db():
    db_path = Path("test_smsbridge.db")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if db_path.exists():
        db_path.unlink()


@pytest.fixture()
def client():
    return TestClient(app)


def login(client: TestClient, email: str, password: str = "change-me") -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture()
def admin_token(client):
    return login(client, "admin@smsbridge.local")


@pytest.fixture()
def user_token(client):
    return login(client, "user@smsbridge.local")
