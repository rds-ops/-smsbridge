from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import httpx
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="smsbridge fake supplier", version="0.1.0")

_reservations: dict[str, dict[str, Any]] = {}

COUNTRY_PREFIX = {"IN": "91", "ID": "62", "KZ": "7", "UZ": "998", "PH": "63", "BR": "55", "MX": "52"}


class ReservationIn(BaseModel):
    request_id: str = Field(min_length=1, max_length=120)
    order_public_id: str = Field(min_length=1, max_length=120)
    service_code: str = Field(min_length=1, max_length=50)
    country_iso2: str = Field(min_length=2, max_length=2)
    operator: str | None = Field(default=None, max_length=80)
    client_price: str
    supplier_reward: str
    timeout_seconds: int = Field(gt=0)


class SmsPayloadIn(BaseModel):
    supplier_sms_id: str = Field(default_factory=lambda: f"fake-sms-{uuid4().hex[:12]}")
    supplier_activation_id: str
    phone_number: str
    phone_from: str | None = "FakeSupplier"
    text: str


def _request_hash(payload: ReservationIn) -> str:
    encoded = json.dumps(payload.model_dump(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fake_phone(country_iso2: str, key: str) -> str:
    prefix = COUNTRY_PREFIX.get(country_iso2.upper(), "1")
    suffix_seed = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:12], 16)
    suffix = str(suffix_seed % 900000000 + 100000000)
    return f"+{prefix}{suffix}"


@app.post("/v1/reservations")
def reserve(payload: ReservationIn, idempotency_key: str = Header(alias="Idempotency-Key")):
    body_hash = _request_hash(payload)
    existing = _reservations.get(idempotency_key)
    if existing:
        if existing["request_hash"] != body_hash:
            raise HTTPException(status_code=409, detail="Idempotency-Key was already used with a different request")
        return existing["response"]

    response = {
        "status": "reserved",
        "supplier_activation_id": f"fake-sup-act-{uuid4().hex[:16]}",
        "phone_number": _fake_phone(payload.country_iso2, idempotency_key),
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=payload.timeout_seconds)).isoformat(),
    }
    _reservations[idempotency_key] = {"request_hash": body_hash, "response": response}
    return response


@app.post("/v1/send-sms")
def send_sms(payload: SmsPayloadIn):
    smsbridge_base_url = os.getenv("SMSBRIDGE_BASE_URL")
    supplier_api_key = os.getenv("SMSBRIDGE_SUPPLIER_API_KEY")
    sms_payload = payload.model_dump()
    if not smsbridge_base_url or not supplier_api_key:
        return {
            "status": "manual",
            "target": "/supplier/v1/sms",
            "payload": sms_payload,
            "message": "Set SMSBRIDGE_BASE_URL and SMSBRIDGE_SUPPLIER_API_KEY to enable callback posting.",
        }

    response = httpx.post(
        f"{smsbridge_base_url.rstrip('/')}/supplier/v1/sms",
        json=sms_payload,
        headers={"Authorization": f"Bearer {supplier_api_key}"},
        timeout=5,
    )
    return {"status": "posted", "smsbridge_status_code": response.status_code, "smsbridge_response": response.json()}
