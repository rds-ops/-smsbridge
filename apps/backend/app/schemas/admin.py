from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.providers.constants import PROVIDER_STATUS_PATTERN, PROVIDER_TYPE_PATTERN
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
    type: str = Field(default="mock", pattern=PROVIDER_TYPE_PATTERN)
    status: str = Field(default="active", pattern=PROVIDER_STATUS_PATTERN)
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


class AdminPaymentIntentOut(ORMModel):
    id: int
    public_id: str
    user_id: int
    provider: str
    currency: str
    amount: Decimal
    status: str
    provider_reference: str | None = None
    idempotency_key: str | None = None
    metadata: dict[str, Any] = Field(validation_alias="intent_metadata")
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None
    succeeded_at: datetime | None = None
    failed_at: datetime | None = None
    cancelled_at: datetime | None = None
    last_webhook_at: datetime | None = None
    last_webhook_event_id: str | None = None
    last_webhook_status: str | None = None
    last_webhook_error: str | None = None
    failed_reason: str | None = None


class PaymentCreditIssueOut(ORMModel):
    issue_type: str
    payment_intent_id: int | None = None
    payment_intent_public_id: str | None = None
    user_id: int | None = None
    provider: str | None = None
    amount: Decimal | None = None
    status: str | None = None
    wallet_transaction_id: int | None = None
    created_at: datetime | None = None


class PaymentCreditReconciliationOut(ORMModel):
    counts: dict[str, int]
    issues: list[PaymentCreditIssueOut]


class SupplierPayoutReconciliationIssueOut(ORMModel):
    issue_type: str
    payout_id: int | None = None
    payout_public_id: str | None = None
    supplier_id: int
    status: str | None = None
    amount: Decimal | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SupplierPayoutReconciliationOut(ORMModel):
    counts: dict[str, int]
    issues: list[SupplierPayoutReconciliationIssueOut]
