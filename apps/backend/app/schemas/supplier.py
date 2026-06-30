from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class SupplierOut(ORMModel):
    id: int
    name: str
    email: str | None = None
    status: str
    reward_percent: Decimal
    balance: Decimal
    held_balance: Decimal
    currency: str
    notes: str | None = None
    reservation_url: str | None = None
    reservation_auth_type: str | None = None
    reservation_timeout_seconds: int | None = None
    reservation_enabled: bool = False
    created_at: datetime
    updated_at: datetime


class SupplierListOut(SupplierOut):
    inventory_count: int = 0


class SupplierCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    email: str | None = Field(default=None, max_length=255)
    status: str = Field(default="pending", pattern="^(pending|active|blocked)$")
    reward_percent: Decimal = Field(default=Decimal("70.00"), ge=0, le=100)
    notes: str | None = Field(default=None, max_length=1000)
    reservation_url: str | None = Field(default=None, max_length=1000)
    reservation_auth_type: str | None = Field(default=None, max_length=50)
    reservation_auth_secret_encrypted: str | None = Field(default=None, max_length=1000)
    reservation_timeout_seconds: int | None = Field(default=None, gt=0)
    reservation_enabled: bool = False


class SupplierPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    email: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, pattern="^(pending|active|blocked)$")
    reward_percent: Decimal | None = Field(default=None, ge=0, le=100)
    notes: str | None = Field(default=None, max_length=1000)
    reservation_url: str | None = Field(default=None, max_length=1000)
    reservation_auth_type: str | None = Field(default=None, max_length=50)
    reservation_auth_secret_encrypted: str | None = Field(default=None, max_length=1000)
    reservation_timeout_seconds: int | None = Field(default=None, gt=0)
    reservation_enabled: bool | None = None


class SupplierApiKeyOut(BaseModel):
    api_key: str
    message: str = "Store this supplier API key now. It will not be shown again."


class SupplierApplicationCreateIn(BaseModel):
    contact_name: str = Field(min_length=2, max_length=160)
    email: str = Field(min_length=5, max_length=255)
    contact_handle: str = Field(min_length=2, max_length=160)
    country_market: str = Field(min_length=2, max_length=120)
    number_type: str = Field(pattern="^(real_sim|virtual_numbers|other)$")
    estimated_daily_volume: int = Field(ge=0, le=10_000_000)
    estimated_monthly_volume: int = Field(ge=0, le=300_000_000)
    integration_availability: str = Field(pattern="^(yes|no|needs_discussion)$")
    inventory_description: str = Field(min_length=20, max_length=3000)
    api_url: str | None = Field(default=None, max_length=1000)
    equipment_details: str | None = Field(default=None, max_length=3000)
    website: str | None = Field(default=None, max_length=1000)


class SupplierApplicationReceivedOut(BaseModel):
    status: str = "received"
    public_id: str
    message: str = "Application received. Our team will review it before issuing supplier access."


class SupplierApplicationOut(ORMModel):
    id: int
    public_id: str
    status: str
    contact_name: str
    email: str
    contact_handle: str
    country_market: str
    number_type: str
    estimated_daily_volume: int
    estimated_monthly_volume: int
    integration_availability: str
    inventory_description: str
    api_url: str | None = None
    equipment_details: str | None = None
    website: str | None = None
    internal_review_note: str | None = None
    reviewed_at: datetime | None = None
    reviewed_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime


class SupplierApplicationPatch(BaseModel):
    status: str | None = Field(default=None, pattern="^(pending|approved|rejected|needs_info)$")
    internal_review_note: str | None = Field(default=None, max_length=3000)


class SupplierMeOut(ORMModel):
    id: int
    name: str
    email: str | None = None
    status: str
    reward_percent: Decimal
    balance: Decimal
    held_balance: Decimal
    currency: str


class SupplierInventoryOut(ORMModel):
    id: int
    supplier_id: int
    service_code: str
    country_iso2: str
    operator: str | None = None
    available_count: int
    success_rate: Decimal | None = None
    avg_sms_time_seconds: int | None = None
    status: str
    last_sync_at: datetime
    created_at: datetime
    updated_at: datetime


class AdminSupplierInventoryOut(SupplierInventoryOut):
    last_reservation_at: datetime | None = None
    last_reservation_error: str | None = None
    failed_reservation_count: int = 0
    last_release_at: datetime | None = None
    last_release_error: str | None = None
    failed_release_count: int = 0


class SupplierInventoryItemIn(BaseModel):
    service_code: str = Field(min_length=2, max_length=50)
    country_iso2: str = Field(min_length=2, max_length=2)
    operator: str | None = Field(default=None, max_length=80)
    available_count: int = Field(ge=0)
    success_rate: Decimal | None = Field(default=None, ge=0, le=100)
    avg_sms_time_seconds: int | None = Field(default=None, ge=0, le=86400)
    status: str = Field(default="active", pattern="^(active|inactive)$")


class SupplierInventoryUpdateIn(BaseModel):
    items: list[SupplierInventoryItemIn] = Field(min_length=1, max_length=500)


class SupplierInventoryUpdateOut(BaseModel):
    updated: int


class SupplierActivationOut(ORMModel):
    id: int
    supplier_id: int
    order_id: int | None = None
    supplier_activation_id: str | None = None
    phone_number: str
    service_code: str
    country_iso2: str
    operator: str | None = None
    status: str
    client_price: Decimal
    supplier_reward: Decimal
    sms_text: str | None = None
    sms_code: str | None = None
    created_at: datetime
    updated_at: datetime


class SupplierActivationSafeOut(BaseModel):
    id: int
    supplier_activation_id: str | None = None
    phone_number: str
    service_code: str
    country_iso2: str
    operator: str | None = None
    status: str
    order_public_id: str | None = None
    sms_count: int = 0
    latest_sms_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SupplierSmsIn(BaseModel):
    supplier_sms_id: str = Field(min_length=1, max_length=120)
    phone_number: str = Field(min_length=5, max_length=40)
    phone_from: str | None = Field(default=None, max_length=120)
    text: str = Field(min_length=1, max_length=1000)
    supplier_activation_id: str | None = Field(default=None, max_length=120)


class SupplierSmsPushOut(BaseModel):
    status: str = "SUCCESS"
    duplicate: bool = False


class SupplierSmsOut(ORMModel):
    id: int
    supplier_id: int
    activation_id: int | None = None
    order_id: int | None = None
    supplier_sms_id: str
    phone_number: str
    phone_from: str | None = None
    text: str
    status: str
    created_at: datetime


class SupplierTransactionOut(ORMModel):
    id: int
    supplier_id: int
    activation_id: int | None = None
    order_id: int | None = None
    type: str
    amount: Decimal
    status: str
    reference: str | None = None
    tx_metadata: dict[str, Any]
    created_at: datetime


class SupplierTransactionSafeOut(BaseModel):
    type: str
    amount: Decimal
    currency: str
    status: str
    reference: str | None = None
    order_public_id: str | None = None
    created_at: datetime


class SupplierReleaseRetryOut(ORMModel):
    id: int
    supplier_activation_id: int
    supplier_id: int
    order_id: int
    retry_type: str
    status: str
    reason: str
    attempt_count: int
    next_retry_at: datetime
    last_error: str | None = None
    last_attempt_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SupplierPayoutRequestCreateIn(BaseModel):
    amount: Decimal = Field(gt=0)
    payout_method: str | None = Field(default=None, max_length=80)
    payout_address: str | None = Field(default=None, max_length=255)


class SupplierPayoutRequestOut(ORMModel):
    id: int
    public_id: str
    supplier_id: int
    amount: Decimal
    currency: str
    status: str
    payout_method: str | None = None
    payout_address: str | None = None
    admin_note: str | None = None
    failure_reason: str | None = None
    requested_at: datetime
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    cancelled_at: datetime | None = None
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class SupplierPayoutActionIn(BaseModel):
    admin_note: str | None = Field(default=None, max_length=1000)
    reason: str | None = Field(default=None, max_length=1000)


class SupplierAdjustmentIn(BaseModel):
    amount: Decimal
    reference: str | None = Field(default=None, max_length=255)
    metadata: dict[str, Any] = {}
