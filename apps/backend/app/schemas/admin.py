from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, UserLimitOut, UserPublic, WalletOut


class UserDetail(UserPublic):
    wallet: WalletOut | None = None
    limit: UserLimitOut | None = None


class UserStatusPatch(BaseModel):
    status: str = Field(pattern="^(active|limited|blocked)$")


class UserLimitsPatch(BaseModel):
    max_orders_per_minute: int | None = Field(default=None, ge=0, le=10000)
    max_orders_per_day: int | None = Field(default=None, ge=0, le=100000)
    max_active_orders: int | None = Field(default=None, ge=0, le=10000)
    max_daily_spend: Decimal | None = Field(default=None, ge=0)
    tier: str | None = Field(default=None, pattern="^(default|verified|wholesale|partner)$")


class DepositIn(BaseModel):
    user_id: int
    amount: Decimal = Field(gt=0)
    reference: str | None = None


class AdjustmentIn(BaseModel):
    user_id: int
    amount: Decimal
    reference: str | None = None
    metadata: dict[str, Any] = {}


class ProviderIn(BaseModel):
    name: str
    code: str
    type: str = "mock"
    status: str = "active"
    priority: int = 100
    base_url: str | None = None
    default_markup_percent: Decimal = Decimal("25.00")


class ProviderOut(ORMModel):
    id: int
    name: str
    code: str
    type: str
    status: str
    priority: int
    base_url: str | None
    default_markup_percent: Decimal


class AdminOrderOut(ORMModel):
    id: int
    public_id: str
    user_id: int
    provider_id: int
    provider_order_id: str | None = None
    service_code: str
    country_iso2: str
    operator: str | None = None
    phone_number: str | None = None
    status: str
    price: Decimal
    provider_cost: Decimal
    sms_code: str | None = None
    sms_text: str | None = None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class OrderEventOut(ORMModel):
    id: int
    order_id: int
    old_status: str | None = None
    new_status: str
    actor_type: str | None = None
    actor_user_id: int | None = None
    reason: str | None = None
    event_metadata: dict[str, Any] | None = None
    created_at: datetime
