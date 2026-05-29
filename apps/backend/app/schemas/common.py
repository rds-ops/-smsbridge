from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserPublic(ORMModel):
    id: int
    email: str
    role: str
    status: str
    tier: str
    locale: str
    api_key_enabled: bool = False
    created_at: datetime


class UserLimitOut(ORMModel):
    max_orders_per_minute: int
    max_orders_per_day: int
    max_active_orders: int
    max_daily_spend: Decimal


class WalletOut(ORMModel):
    balance: Decimal
    held_balance: Decimal
    currency: str


class ServiceOut(ORMModel):
    code: str
    name_ru: str
    name_en: str
    category: str | None = None
    is_active: bool


class CountryOut(ORMModel):
    iso2: str
    name_ru: str
    name_en: str
    is_active: bool


class BuyerPriceOut(ORMModel):
    service_code: str
    country_iso2: str
    operator: str | None = None
    provider_code: str | None = None
    provider_name: str | None = None
    final_price: Decimal
    available_count: int
    delivery_rate: Decimal


class OrderOut(ORMModel):
    public_id: str
    service_code: str
    country_iso2: str
    operator: str | None = None
    phone_number: str | None = None
    status: str
    price: Decimal
    sms_code: str | None = None
    sms_text: str | None = None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class OrderCreate(BaseModel):
    service_code: str = Field(min_length=2, max_length=50)
    country_iso2: str = Field(min_length=2, max_length=2)
    operator: str | None = Field(default=None, max_length=80)


class MessageOut(BaseModel):
    message: str


class AuditLogOut(ORMModel):
    id: int
    actor_user_id: int | None
    action: str
    entity_type: str
    entity_id: str | None
    log_metadata: dict[str, Any]
    created_at: datetime


class ApiRequestLogOut(ORMModel):
    id: int
    user_id: int | None
    endpoint: str
    method: str
    ip_address: str | None
    status_code: int
    created_at: datetime
