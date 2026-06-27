from __future__ import annotations
from decimal import Decimal
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

PRODUCTION_LIKE_ENVIRONMENTS = {"production", "prod", "staging", "stage"}
UNSAFE_SECRET_KEYS = {
    "change-me",
    "change-this-secret",
    "change-this-in-production",
    "changeme",
    "secret",
    "test-secret",
}
UNSAFE_INTERNAL_WEBHOOK_SECRETS = {"change-me", "changeme", "secret", "test-secret"}
DEFAULT_ADMIN_PASSWORDS = {"change-me"}
MIN_PRODUCTION_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    app_name: str = "smsbridge"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://smsbridge:smsbridge@postgres:5432/smsbridge"
    redis_url: str = "redis://redis:6379/0"
    secret_key: str = "change-this-secret"
    admin_seed_password: str = "change-me"
    internal_webhook_secret: str = "change-me"
    access_token_minutes: int = 60
    refresh_token_minutes: int = 60 * 24 * 14
    cors_origins: str = "http://localhost:3000"
    mock_success_rate: float = 0.85
    mock_sms_delay_seconds: int = 10
    mock_order_timeout_seconds: int = 120
    rate_limit_per_minute: int = 120
    rate_limit_anonymous_per_minute: int | None = None
    rate_limit_user_default_per_minute: int | None = None
    rate_limit_user_verified_per_minute: int | None = None
    rate_limit_user_wholesale_per_minute: int | None = None
    rate_limit_user_partner_per_minute: int | None = None
    rate_limit_supplier_per_minute: int | None = None
    rate_limit_admin_per_minute: int | None = None
    api_request_log_retention_days: int = 90
    payment_webhook_event_retention_days: int = 180
    supplier_release_retry_retention_days: int = 180
    supplier_payout_min_amount: Decimal = Decimal("1.0000")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production_like(self) -> bool:
        return self.environment.strip().lower() in PRODUCTION_LIKE_ENVIRONMENTS


def validate_production_safety(config: Settings) -> None:
    if not config.is_production_like:
        return

    secret_key = config.secret_key.strip()
    if not secret_key:
        raise RuntimeError("Unsafe production configuration: SECRET_KEY must be at least 32 characters")
    if secret_key in UNSAFE_SECRET_KEYS:
        raise RuntimeError("Unsafe production configuration: SECRET_KEY uses a known default value")
    if len(secret_key) < MIN_PRODUCTION_SECRET_KEY_LENGTH:
        raise RuntimeError("Unsafe production configuration: SECRET_KEY must be at least 32 characters")

    if config.admin_seed_password in DEFAULT_ADMIN_PASSWORDS:
        raise RuntimeError("Unsafe production configuration: ADMIN_SEED_PASSWORD uses a default password")

    internal_secret = config.internal_webhook_secret.strip()
    if not internal_secret:
        raise RuntimeError("Unsafe production configuration: INTERNAL_WEBHOOK_SECRET must not be empty")
    if internal_secret in UNSAFE_INTERNAL_WEBHOOK_SECRETS:
        raise RuntimeError("Unsafe production configuration: INTERNAL_WEBHOOK_SECRET uses a known default value")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

