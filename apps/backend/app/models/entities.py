from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.providers.constants import ALLOWED_PROVIDER_STATUSES, ALLOWED_PROVIDER_TYPES


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    tier: Mapped[str] = mapped_column(String(20), default="default", nullable=False)
    api_key_hash: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    locale: Mapped[str] = mapped_column(String(2), default="en", nullable=False)

    limit: Mapped["UserLimit"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")
    wallet: Mapped["Wallet"] = relationship(back_populates="user", uselist=False, cascade="all, delete-orphan")

    @property
    def api_key_enabled(self) -> bool:
        return bool(self.api_key_hash)


BUYER_API_KEY_STATUSES = ("active", "revoked")
RISK_ACTIONS = ("watch", "note", "clear_watch", "mark_reviewed")


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jti: Mapped[str] = mapped_column(String(36), unique=True, default=lambda: str(uuid4()), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ip_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    user: Mapped[User] = relationship()

    __table_args__ = (
        Index("ix_refresh_sessions_user_created_at", "user_id", "created_at"),
        Index("ix_refresh_sessions_user_revoked_at", "user_id", "revoked_at"),
    )


class LoginAttempt(Base, TimestampMixin):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identifier_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True, nullable=True)

    user: Mapped[Optional[User]] = relationship()

    __table_args__ = (
        CheckConstraint("failed_attempts >= 0", name="ck_login_attempts_failed_attempts_non_negative"),
        Index("ix_login_attempts_user_id", "user_id"),
    )


class BuyerApiKey(Base):
    __tablename__ = "buyer_api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid4()), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True, nullable=False)
    scopes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship()

    __table_args__ = (
        CheckConstraint(f"status in {BUYER_API_KEY_STATUSES}", name="ck_buyer_api_keys_status_allowed"),
    )


class UserRiskAction(Base):
    __tablename__ = "user_risk_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped[User] = relationship(foreign_keys=[user_id])
    actor_user: Mapped[Optional[User]] = relationship(foreign_keys=[actor_user_id])

    __table_args__ = (
        CheckConstraint(f"action in {RISK_ACTIONS}", name="ck_user_risk_actions_action_allowed"),
        Index("ix_user_risk_actions_user_created_at", "user_id", "created_at"),
    )


class UserLimit(Base, TimestampMixin):
    __tablename__ = "user_limits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    max_orders_per_minute: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    max_orders_per_day: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    max_active_orders: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    max_daily_spend: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("10.00"), nullable=False)

    user: Mapped[User] = relationship(back_populates="limit")


class Wallet(Base, TimestampMixin):
    __tablename__ = "wallets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.00"), nullable=False)
    held_balance: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.00"), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)

    user: Mapped[User] = relationship(back_populates="wallet")

    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_wallets_balance_non_negative"),
        CheckConstraint("held_balance >= 0", name="ck_wallets_held_balance_non_negative"),
    )


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"), index=True, nullable=True)
    payment_intent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("payment_intents.id"), index=True, nullable=True)
    type: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tx_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("order_id", "type", "status", name="uq_wallet_order_type_status"),
        Index(
            "uq_wallet_transactions_payment_intent_id_not_null",
            "payment_intent_id",
            unique=True,
            postgresql_where=text("payment_intent_id IS NOT NULL"),
            sqlite_where=text("payment_intent_id IS NOT NULL"),
        ),
    )


class Provider(Base, TimestampMixin):
    __tablename__ = "providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    type: Mapped[str] = mapped_column(String(20), default="mock", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    default_markup_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("25.00"), nullable=False)

    __table_args__ = (
        CheckConstraint(f"type in {ALLOWED_PROVIDER_TYPES}", name="ck_providers_type_allowed"),
        CheckConstraint(f"status in {ALLOWED_PROVIDER_STATUSES}", name="ck_providers_status_allowed"),
    )


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name_ru: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Country(Base):
    __tablename__ = "countries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    iso2: Mapped[str] = mapped_column(String(2), unique=True, index=True, nullable=False)
    name_ru: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Price(Base):
    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), index=True, nullable=False)
    service_code: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    country_iso2: Mapped[str] = mapped_column(String(2), index=True, nullable=False)
    operator: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    provider_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    final_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    available_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivery_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("90.00"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    provider: Mapped[Provider] = relationship()

    __table_args__ = (
        Index(
            "uq_prices_provider_service_country_operator_null",
            "provider_id",
            "service_code",
            "country_iso2",
            unique=True,
            postgresql_where=text("operator IS NULL"),
            sqlite_where=text("operator IS NULL"),
        ),
        Index(
            "uq_prices_provider_service_country_operator_value",
            "provider_id",
            "service_code",
            "country_iso2",
            "operator",
            unique=True,
            postgresql_where=text("operator IS NOT NULL"),
            sqlite_where=text("operator IS NOT NULL"),
        ),
    )

    @property
    def provider_code(self) -> str | None:
        return self.provider.code if self.provider else None

    @property
    def provider_name(self) -> str | None:
        return self.provider.name if self.provider else None


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid4()), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    provider_id: Mapped[int] = mapped_column(ForeignKey("providers.id"), index=True, nullable=False)
    provider_order_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    service_code: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    country_iso2: Mapped[str] = mapped_column(String(2), index=True, nullable=False)
    operator: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(30), index=True, default="created", nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    provider_cost: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    sms_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sms_text: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    provider: Mapped[Provider] = relationship()

    __table_args__ = (
        Index("ix_orders_user_created_at", "user_id", "created_at"),
        Index("ix_orders_status_expires_at", "status", "expires_at"),
        Index("ix_orders_status_created_at", "status", "created_at"),
    )


class OrderEvent(Base):
    __tablename__ = "order_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True, nullable=False)
    old_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    event_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    order: Mapped[Order] = relationship()
    actor_user: Mapped[Optional[User]] = relationship()

    __table_args__ = (
        Index("ix_order_events_order_created_at", "order_id", "created_at"),
    )


class IdempotencyKey(Base, TimestampMixin):
    __tablename__ = "idempotency_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="in_progress", nullable=False)

    order: Mapped[Optional[Order]] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "action", "key", name="uq_idempotency_user_action_key"),
    )


PAYMENT_INTENT_STATUSES = ("created", "pending", "succeeded", "failed", "cancelled", "expired")


class PaymentIntent(Base, TimestampMixin):
    __tablename__ = "payment_intents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid4()), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), index=True, default="created", nullable=False)
    provider_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    request_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    intent_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    succeeded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_webhook_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_webhook_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_webhook_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    last_webhook_error: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    failed_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    user: Mapped[User] = relationship()

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payment_intents_amount_positive"),
        CheckConstraint(f"status in {PAYMENT_INTENT_STATUSES}", name="ck_payment_intents_status_allowed"),
        Index("ix_payment_intents_user_created_at", "user_id", "created_at"),
        Index("ix_payment_intents_status_created_at", "status", "created_at"),
        Index("ix_payment_intents_provider_created_at", "provider", "created_at"),
        Index(
            "uq_payment_intents_user_idempotency_key_not_null",
            "user_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
            sqlite_where=text("idempotency_key IS NOT NULL"),
        ),
    )


PAYMENT_WEBHOOK_EVENT_STATUSES = ("processed", "duplicate", "ignored", "failed")


class PaymentWebhookEvent(Base):
    __tablename__ = "payment_webhook_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    provider: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    external_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint(f"status in {PAYMENT_WEBHOOK_EVENT_STATUSES}", name="ck_payment_webhook_events_status_allowed"),
        Index(
            "uq_payment_webhook_events_provider_external_event_id",
            "provider",
            "external_event_id",
            unique=True,
            postgresql_where=text("external_event_id IS NOT NULL"),
            sqlite_where=text("external_event_id IS NOT NULL"),
        ),
        UniqueConstraint("provider", "payload_hash", name="uq_payment_webhook_events_provider_payload_hash"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    log_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ApiRequestLog(Base):
    __tablename__ = "api_request_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), index=True, nullable=True)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"), index=True, nullable=True)
    buyer_api_key_id: Mapped[Optional[int]] = mapped_column(ForeignKey("buyer_api_keys.id"), index=True, nullable=True)
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    request_id: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_api_request_logs_user_created_at", "user_id", "created_at"),
        Index("ix_api_request_logs_supplier_created_at", "supplier_id", "created_at"),
        Index("ix_api_request_logs_buyer_key_created_at", "buyer_api_key_id", "created_at"),
        Index("ix_api_request_logs_status_created_at", "status_code", "created_at"),
    )


class SystemSetting(Base, TimestampMixin):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    value: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, nullable=False)
    api_key_hash: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True)
    reward_percent: Mapped[Decimal] = mapped_column(Numeric(8, 4), default=Decimal("70.00"), nullable=False)
    balance: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.00"), nullable=False)
    held_balance: Mapped[Decimal] = mapped_column(Numeric(12, 4), default=Decimal("0.00"), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    reservation_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    reservation_auth_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    reservation_auth_secret_encrypted: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    reservation_timeout_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    reservation_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_suppliers_balance_non_negative"),
        CheckConstraint("held_balance >= 0", name="ck_suppliers_held_balance_non_negative"),
    )


SUPPLIER_APPLICATION_STATUSES = ("pending", "approved", "rejected", "needs_info")
SUPPLIER_APPLICATION_NUMBER_TYPES = ("real_sim", "virtual_numbers", "other")
SUPPLIER_APPLICATION_INTEGRATION_AVAILABILITY = ("yes", "no", "needs_discussion")


class SupplierApplication(Base, TimestampMixin):
    __tablename__ = "supplier_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid4()), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, nullable=False)
    contact_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    contact_handle: Mapped[str] = mapped_column(String(160), nullable=False)
    country_market: Mapped[str] = mapped_column(String(120), nullable=False)
    number_type: Mapped[str] = mapped_column(String(40), nullable=False)
    estimated_daily_volume: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_monthly_volume: Mapped[int] = mapped_column(Integer, nullable=False)
    integration_availability: Mapped[str] = mapped_column(String(40), nullable=False)
    inventory_description: Mapped[str] = mapped_column(Text, nullable=False)
    api_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    equipment_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    internal_review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    reviewed_by: Mapped[Optional[User]] = relationship()

    __table_args__ = (
        CheckConstraint(f"status in {SUPPLIER_APPLICATION_STATUSES}", name="ck_supplier_applications_status_allowed"),
        CheckConstraint(f"number_type in {SUPPLIER_APPLICATION_NUMBER_TYPES}", name="ck_supplier_applications_number_type_allowed"),
        CheckConstraint(
            f"integration_availability in {SUPPLIER_APPLICATION_INTEGRATION_AVAILABILITY}",
            name="ck_supplier_applications_integration_allowed",
        ),
        CheckConstraint("estimated_daily_volume >= 0", name="ck_supplier_applications_daily_volume_non_negative"),
        CheckConstraint("estimated_monthly_volume >= 0", name="ck_supplier_applications_monthly_volume_non_negative"),
        Index("ix_supplier_applications_status_created_at", "status", "created_at"),
        Index("ix_supplier_applications_email_created_at", "email", "created_at"),
    )


class SupplierInventory(Base, TimestampMixin):
    __tablename__ = "supplier_inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True, nullable=False)
    service_code: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    country_iso2: Mapped[str] = mapped_column(String(2), index=True, nullable=False)
    operator: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    available_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    success_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    avg_sms_time_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True, nullable=False)
    last_sync_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_reservation_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reservation_error: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    failed_reservation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_release_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_release_error: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    failed_release_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    supplier: Mapped[Supplier] = relationship()

    __table_args__ = (
        Index("ix_supplier_inventory_supplier_updated_at", "supplier_id", "updated_at"),
        Index(
            "ix_supplier_inventory_lookup_active",
            "status",
            "service_code",
            "country_iso2",
            "operator",
        ),
        Index(
            "uq_supplier_inventory_supplier_service_country_operator_null",
            "supplier_id",
            "service_code",
            "country_iso2",
            unique=True,
            postgresql_where=text("operator IS NULL"),
            sqlite_where=text("operator IS NULL"),
        ),
        Index(
            "uq_supplier_inventory_supplier_service_country_operator_value",
            "supplier_id",
            "service_code",
            "country_iso2",
            "operator",
            unique=True,
            postgresql_where=text("operator IS NOT NULL"),
            sqlite_where=text("operator IS NOT NULL"),
        ),
    )


class SupplierActivation(Base, TimestampMixin):
    __tablename__ = "supplier_activations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True, nullable=False)
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"), unique=True, index=True, nullable=True)
    supplier_activation_id: Mapped[Optional[str]] = mapped_column(String(120), index=True, nullable=True)
    phone_number: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    service_code: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    country_iso2: Mapped[str] = mapped_column(String(2), index=True, nullable=False)
    operator: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="reserved", index=True, nullable=False)
    client_price: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    supplier_reward: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    sms_text: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sms_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    supplier: Mapped[Supplier] = relationship()
    order: Mapped[Optional[Order]] = relationship()

    __table_args__ = (
        UniqueConstraint("supplier_id", "supplier_activation_id", name="uq_supplier_activation_external_id"),
        Index("ix_supplier_activations_supplier_created_at", "supplier_id", "created_at"),
        Index("ix_supplier_activations_supplier_phone_status", "supplier_id", "phone_number", "status"),
    )


class SupplierReleaseRetry(Base, TimestampMixin):
    __tablename__ = "supplier_release_retries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_activation_id: Mapped[int] = mapped_column(ForeignKey("supplier_activations.id"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True, nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True, nullable=False)
    retry_type: Mapped[str] = mapped_column(String(20), default="release", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True, nullable=False)
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    activation: Mapped[SupplierActivation] = relationship()
    supplier: Mapped[Supplier] = relationship()
    order: Mapped[Order] = relationship()

    __table_args__ = (
        UniqueConstraint("supplier_activation_id", "retry_type", name="uq_supplier_release_retry_activation_type"),
        CheckConstraint("attempt_count >= 0", name="ck_supplier_release_retries_attempt_count_non_negative"),
        Index("ix_supplier_release_retries_status_next_retry_at", "status", "next_retry_at"),
    )


SUPPLIER_PAYOUT_REQUEST_STATUSES = ("requested", "approved", "rejected", "cancelled", "paid", "failed")


class SupplierPayoutRequest(Base, TimestampMixin):
    __tablename__ = "supplier_payout_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, index=True, default=lambda: str(uuid4()), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="requested", index=True, nullable=False)
    payout_method: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    payout_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    admin_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    supplier: Mapped[Supplier] = relationship()

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_supplier_payout_requests_amount_positive"),
        CheckConstraint(f"status in {SUPPLIER_PAYOUT_REQUEST_STATUSES}", name="ck_supplier_payout_requests_status_allowed"),
        Index("ix_supplier_payout_requests_supplier_created_at", "supplier_id", "created_at"),
        Index("ix_supplier_payout_requests_status_created_at", "status", "created_at"),
        Index("ix_supplier_payout_requests_status_updated_at", "status", "updated_at"),
    )


class SupplierSms(Base):
    __tablename__ = "supplier_sms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True, nullable=False)
    activation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("supplier_activations.id"), index=True, nullable=True)
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"), index=True, nullable=True)
    supplier_sms_id: Mapped[str] = mapped_column(String(120), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    phone_from: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    text: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="received", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    supplier: Mapped[Supplier] = relationship()
    activation: Mapped[Optional[SupplierActivation]] = relationship()
    order: Mapped[Optional[Order]] = relationship()

    __table_args__ = (UniqueConstraint("supplier_id", "supplier_sms_id", name="uq_supplier_sms_external_id"),)


class SmsMessage(Base):
    __tablename__ = "sms_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    supplier_id: Mapped[Optional[int]] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    supplier_activation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("supplier_activations.id"), nullable=True)
    provider_id: Mapped[Optional[int]] = mapped_column(ForeignKey("providers.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    external_message_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    phone_from: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    text: Mapped[str] = mapped_column(String(1000), nullable=False)
    parsed_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    order: Mapped[Order] = relationship()
    supplier: Mapped[Optional[Supplier]] = relationship()
    supplier_activation: Mapped[Optional[SupplierActivation]] = relationship()
    provider: Mapped[Optional[Provider]] = relationship()

    __table_args__ = (
        Index("ix_sms_messages_order_id", "order_id"),
        Index("ix_sms_messages_order_created_at", "order_id", "created_at"),
        Index("ix_sms_messages_supplier_id", "supplier_id"),
        Index("ix_sms_messages_provider_id", "provider_id"),
        Index("ix_sms_messages_provider_created_at", "provider_id", "created_at"),
        Index("ix_sms_messages_created_at", "created_at"),
        UniqueConstraint("source", "supplier_id", "external_message_id", name="uq_sms_messages_source_supplier_external_id"),
    )


class SupplierTransaction(Base):
    __tablename__ = "supplier_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True, nullable=False)
    activation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("supplier_activations.id"), index=True, nullable=True)
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"), index=True, nullable=True)
    type: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tx_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    supplier: Mapped[Supplier] = relationship()
    activation: Mapped[Optional[SupplierActivation]] = relationship()
    order: Mapped[Optional[Order]] = relationship()

    __table_args__ = (
        UniqueConstraint("supplier_id", "order_id", "type", "status", name="uq_supplier_order_tx"),
        Index("ix_supplier_transactions_supplier_created_at", "supplier_id", "created_at"),
        Index("ix_supplier_transactions_reference_type_status", "reference", "type", "status"),
    )
