from __future__ import annotations
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


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
    type: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="completed", nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tx_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (UniqueConstraint("order_id", "type", "status", name="uq_wallet_order_type_status"),)


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
        UniqueConstraint("provider_id", "service_code", "country_iso2", "operator", name="uq_provider_price"),
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
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


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

    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_suppliers_balance_non_negative"),
        CheckConstraint("held_balance >= 0", name="ck_suppliers_held_balance_non_negative"),
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

    supplier: Mapped[Supplier] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "supplier_id",
            "service_code",
            "country_iso2",
            "operator",
            name="uq_supplier_inventory_key",
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
        Index("ix_sms_messages_supplier_id", "supplier_id"),
        Index("ix_sms_messages_provider_id", "provider_id"),
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
    )
