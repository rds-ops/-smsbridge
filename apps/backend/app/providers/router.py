from __future__ import annotations
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import api_error
from app.models import Price, Provider
from app.providers.base import BaseProvider
from app.providers.constants import ALLOWED_PROVIDER_TYPES
from app.providers.five_sim import FiveSimProvider
from app.providers.mock import MockProvider
from app.providers.sms_activate import SmsActivateProvider
from app.providers.sms_man import SmsManProvider
from app.providers.supplier_pool import SupplierPoolProvider


def get_adapter(provider: Provider) -> BaseProvider:
    if provider.type == "supplier_pool":
        return SupplierPoolProvider()
    if provider.type == "mock":
        return MockProvider(provider.code)
    if provider.type == "five_sim" or provider.code == "5sim":
        return FiveSimProvider()
    if provider.type == "sms_activate" or provider.code == "sms_activate":
        return SmsActivateProvider()
    if provider.type == "sms_man" or provider.code == "sms_man":
        return SmsManProvider()
    if provider.type not in ALLOWED_PROVIDER_TYPES:
        raise api_error(502, "PROVIDER_UNAVAILABLE", "Provider type is unsupported")
    raise api_error(502, "PROVIDER_UNAVAILABLE", "Provider adapter is not configured")


def final_price(provider_cost: Decimal, markup_percent: Decimal) -> Decimal:
    return (provider_cost * (Decimal("1") + markup_percent / Decimal("100"))).quantize(Decimal("0.0001"))


def candidate_prices(db: Session, service_code: str, country_iso2: str, operator: str | None = None) -> list[Price]:
    stmt = (
        select(Price)
        .join(Provider, Price.provider_id == Provider.id)
        .where(
            Provider.status == "active",
            Price.service_code == service_code,
            Price.country_iso2 == country_iso2.upper(),
            Price.available_count > 0,
        )
        .order_by(Provider.priority.desc(), Price.final_price.asc())
    )
    if operator:
        stmt = stmt.where((Price.operator == operator) | (Price.operator.is_(None)))
    return list(db.scalars(stmt))
