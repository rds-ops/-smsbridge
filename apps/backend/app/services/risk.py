from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ApiRequestLog, BuyerApiKey, Order, User


ACTIVE_ORDER_STATUSES = ("created", "waiting_sms", "sms_received")

# Conservative beta thresholds: these only surface risk for admin review.
# They do not block users or mutate account/order state.
MIN_RATE_SAMPLE_ORDERS = 5
MEDIUM_BAD_ORDER_RATE = 0.35
HIGH_BAD_ORDER_RATE = 0.50
MEDIUM_ORDERS_LAST_1H = 10
HIGH_ORDERS_LAST_1H = 20
MEDIUM_API_REQUESTS_LAST_1H = 300
HIGH_API_REQUESTS_LAST_1H = 1000
MEDIUM_REVOKED_API_KEYS = 3
HIGH_REVOKED_API_KEYS = 6


@dataclass(frozen=True)
class UserRiskSummary:
    user_id: int
    email: str
    status: str
    tier: str
    risk_level: str
    risk_score: int
    total_orders: int
    active_orders: int
    cancelled_orders: int
    expired_orders: int
    failed_orders: int
    completed_orders: int
    cancellation_rate: float
    expiration_rate: float
    failed_rate: float
    orders_last_1h: int
    orders_last_24h: int
    api_requests_last_1h: int
    managed_api_key_count: int
    revoked_api_key_count: int
    last_order_at: datetime | None
    last_api_request_at: datetime | None


def get_user_risk_summary(db: Session, user: User, *, now: datetime | None = None) -> UserRiskSummary:
    now = now or datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    one_day_ago = now - timedelta(hours=24)

    status_rows = db.execute(
        select(Order.status, func.count(Order.id)).where(Order.user_id == user.id).group_by(Order.status)
    ).all()
    status_counts = {status: int(count) for status, count in status_rows}

    total_orders = sum(status_counts.values())
    cancelled_orders = status_counts.get("cancelled", 0)
    expired_orders = status_counts.get("expired", 0)
    failed_orders = status_counts.get("failed", 0)
    completed_orders = status_counts.get("completed", 0)
    active_orders = sum(status_counts.get(status, 0) for status in ACTIVE_ORDER_STATUSES)

    orders_last_1h = int(
        db.scalar(select(func.count(Order.id)).where(Order.user_id == user.id, Order.created_at >= one_hour_ago)) or 0
    )
    orders_last_24h = int(
        db.scalar(select(func.count(Order.id)).where(Order.user_id == user.id, Order.created_at >= one_day_ago)) or 0
    )
    api_requests_last_1h = int(
        db.scalar(
            select(func.count(ApiRequestLog.id)).where(
                ApiRequestLog.user_id == user.id,
                ApiRequestLog.created_at >= one_hour_ago,
            )
        )
        or 0
    )
    managed_api_key_count = int(
        db.scalar(select(func.count(BuyerApiKey.id)).where(BuyerApiKey.user_id == user.id)) or 0
    )
    revoked_api_key_count = int(
        db.scalar(
            select(func.count(BuyerApiKey.id)).where(
                BuyerApiKey.user_id == user.id,
                BuyerApiKey.status == "revoked",
            )
        )
        or 0
    )
    last_order_at = db.scalar(select(func.max(Order.created_at)).where(Order.user_id == user.id))
    last_api_request_at = db.scalar(select(func.max(ApiRequestLog.created_at)).where(ApiRequestLog.user_id == user.id))

    cancellation_rate = _rate(cancelled_orders, total_orders)
    expiration_rate = _rate(expired_orders, total_orders)
    failed_rate = _rate(failed_orders, total_orders)
    bad_order_rate = _rate(cancelled_orders + expired_orders + failed_orders, total_orders)
    risk_level, risk_score = _risk_level(
        total_orders=total_orders,
        bad_order_rate=bad_order_rate,
        orders_last_1h=orders_last_1h,
        api_requests_last_1h=api_requests_last_1h,
        revoked_api_key_count=revoked_api_key_count,
    )

    return UserRiskSummary(
        user_id=user.id,
        email=user.email,
        status=user.status,
        tier=user.tier,
        risk_level=risk_level,
        risk_score=risk_score,
        total_orders=total_orders,
        active_orders=active_orders,
        cancelled_orders=cancelled_orders,
        expired_orders=expired_orders,
        failed_orders=failed_orders,
        completed_orders=completed_orders,
        cancellation_rate=cancellation_rate,
        expiration_rate=expiration_rate,
        failed_rate=failed_rate,
        orders_last_1h=orders_last_1h,
        orders_last_24h=orders_last_24h,
        api_requests_last_1h=api_requests_last_1h,
        managed_api_key_count=managed_api_key_count,
        revoked_api_key_count=revoked_api_key_count,
        last_order_at=last_order_at,
        last_api_request_at=last_api_request_at,
    )


def list_user_risk_summaries(
    db: Session,
    *,
    risk_level: str | None = None,
    user_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[UserRiskSummary]:
    stmt = select(User)
    if user_id is not None:
        stmt = stmt.where(User.id == user_id)
    users = list(db.scalars(stmt.order_by(User.created_at.desc()).limit(500)))
    summaries = [get_user_risk_summary(db, user) for user in users]
    if risk_level:
        summaries = [summary for summary in summaries if summary.risk_level == risk_level]
    summaries.sort(
        key=lambda summary: (
            summary.risk_score,
            summary.orders_last_1h,
            summary.api_requests_last_1h,
            summary.total_orders,
            summary.last_order_at or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    start = max(0, offset)
    end = start + max(1, min(limit, 500))
    return summaries[start:end]


def _rate(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(count / total, 4)


def _risk_level(
    *,
    total_orders: int,
    bad_order_rate: float,
    orders_last_1h: int,
    api_requests_last_1h: int,
    revoked_api_key_count: int,
) -> tuple[str, int]:
    score = 0

    if total_orders >= MIN_RATE_SAMPLE_ORDERS and bad_order_rate > HIGH_BAD_ORDER_RATE:
        score += 60
    elif total_orders >= MIN_RATE_SAMPLE_ORDERS and bad_order_rate > MEDIUM_BAD_ORDER_RATE:
        score += 30

    if orders_last_1h > HIGH_ORDERS_LAST_1H:
        score += 60
    elif orders_last_1h > MEDIUM_ORDERS_LAST_1H:
        score += 30

    if api_requests_last_1h > HIGH_API_REQUESTS_LAST_1H:
        score += 40
    elif api_requests_last_1h > MEDIUM_API_REQUESTS_LAST_1H:
        score += 20

    if revoked_api_key_count >= HIGH_REVOKED_API_KEYS:
        score += 25
    elif revoked_api_key_count >= MEDIUM_REVOKED_API_KEYS:
        score += 10

    if score >= 60:
        return "high", score
    if score >= 30:
        return "medium", score
    return "low", score
