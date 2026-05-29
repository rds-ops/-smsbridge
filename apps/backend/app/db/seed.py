from __future__ import annotations
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings, validate_production_safety
from app.core.security import hash_password
from app.models import Country, Price, Provider, Service, SystemSetting, User, UserLimit, Wallet
from app.providers.mock import COUNTRIES, SERVICES
from app.providers.router import final_price

SERVICE_NAMES = {
    "telegram": ("Telegram", "Telegram"),
    "whatsapp": ("WhatsApp", "WhatsApp"),
    "google": ("Google", "Google"),
    "facebook": ("Facebook", "Facebook"),
    "amazon": ("Amazon", "Amazon"),
    "openai": ("OpenAI", "OpenAI"),
}

COUNTRY_NAMES = {
    "IN": ("Индия", "India"),
    "ID": ("Индонезия", "Indonesia"),
    "KZ": ("Казахстан", "Kazakhstan"),
    "UZ": ("Узбекистан", "Uzbekistan"),
    "PH": ("Филиппины", "Philippines"),
    "BR": ("Бразилия", "Brazil"),
    "MX": ("Мексика", "Mexico"),
}


def seed(db: Session) -> None:
    validate_production_safety(settings)
    if not db.scalar(select(User).where(User.email == "admin@smsbridge.local")):
        admin = User(
            email="admin@smsbridge.local",
            password_hash=hash_password(settings.admin_seed_password),
            role="admin",
            status="active",
            tier="wholesale",
            locale="en",
        )
        admin.limit = UserLimit(max_orders_per_minute=100, max_orders_per_day=1000, max_active_orders=100, max_daily_spend=Decimal("10000"))
        admin.wallet = Wallet(balance=Decimal("0"))
        db.add(admin)

    if not db.scalar(select(User).where(User.email == "user@smsbridge.local")):
        user = User(email="user@smsbridge.local", password_hash=hash_password("change-me"), locale="en")
        user.limit = UserLimit()
        user.wallet = Wallet(balance=Decimal("25.00"))
        db.add(user)

    for code in SERVICES:
        if not db.scalar(select(Service).where(Service.code == code)):
            ru, en = SERVICE_NAMES[code]
            db.add(Service(code=code, name_ru=ru, name_en=en, category="verification"))

    for iso2 in COUNTRIES:
        if not db.scalar(select(Country).where(Country.iso2 == iso2)):
            ru, en = COUNTRY_NAMES[iso2]
            db.add(Country(iso2=iso2, name_ru=ru, name_en=en))

    db.flush()
    provider = db.scalar(select(Provider).where(Provider.code == "mock"))
    if not provider:
        provider = Provider(
            name="MockProvider",
            code="mock",
            type="mock",
            status="active",
            priority=100,
            default_markup_percent=Decimal("25.00"),
        )
        db.add(provider)
        db.flush()

    supplier_pool = db.scalar(select(Provider).where(Provider.code == "supplier_pool"))
    if not supplier_pool:
        db.add(
            Provider(
                name="Supplier Pool",
                code="supplier_pool",
                type="supplier_pool",
                status="active",
                priority=150,
                default_markup_percent=Decimal("0.00"),
            )
        )

    for service_idx, service_code in enumerate(SERVICES):
        for country_idx, country_iso2 in enumerate(COUNTRIES):
            exists = db.scalar(
                select(Price).where(
                    Price.provider_id == provider.id,
                    Price.service_code == service_code,
                    Price.country_iso2 == country_iso2,
                    Price.operator.is_(None),
                )
            )
            if exists:
                continue
            provider_cost = Decimal("0.35") + Decimal(str((service_idx + country_idx) % 5)) / Decimal("10")
            db.add(
                Price(
                    provider_id=provider.id,
                    service_code=service_code,
                    country_iso2=country_iso2,
                    operator=None,
                    provider_cost=provider_cost,
                    final_price=final_price(provider_cost, provider.default_markup_percent),
                    available_count=25,
                    delivery_rate=Decimal("88.50"),
                )
            )

    for key, value in {
        "acceptable_use_policy_version": {"version": "placeholder"},
        "manual_payments_only": {"enabled": True},
        "abuse_contact": {"email": "abuse@smsbridge.local"},
    }.items():
        if not db.scalar(select(SystemSetting).where(SystemSetting.key == key)):
            db.add(SystemSetting(key=key, value=value))

    db.commit()


if __name__ == "__main__":
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        seed(session)
    finally:
        session.close()
