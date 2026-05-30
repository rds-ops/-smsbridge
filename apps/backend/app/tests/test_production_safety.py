from __future__ import annotations

import pytest

from app.core.config import Settings, validate_production_safety


def settings(**kwargs) -> Settings:
    defaults = {
        "environment": "local",
        "secret_key": "change-this-in-production",
        "admin_seed_password": "change-me",
        "internal_webhook_secret": "change-me",
    }
    defaults.update(kwargs)
    return Settings(**defaults)


def test_local_env_allows_dev_defaults():
    validate_production_safety(settings())


@pytest.mark.parametrize("environment", ["production", "prod", "staging", "stage"])
def test_production_like_env_rejects_default_secret_key(environment):
    with pytest.raises(RuntimeError, match="SECRET_KEY uses a known default value"):
        validate_production_safety(settings(environment=environment, secret_key="change-this-in-production"))


@pytest.mark.parametrize("secret_key", ["", "short-secret"])
def test_production_env_rejects_empty_or_weak_secret_key(secret_key):
    with pytest.raises(RuntimeError, match="SECRET_KEY must be at least 32 characters"):
        validate_production_safety(settings(environment="production", secret_key=secret_key))


def test_production_env_rejects_default_admin_seed_password():
    with pytest.raises(RuntimeError, match="ADMIN_SEED_PASSWORD uses a default password"):
        validate_production_safety(
            settings(
                environment="production",
                secret_key="prod-secret-key-with-more-than-32-characters",
                admin_seed_password="change-me",
            )
        )


def test_production_env_accepts_strong_custom_values():
    validate_production_safety(
        settings(
            environment="production",
            secret_key="prod-secret-key-with-more-than-32-characters",
            admin_seed_password="not-the-default-admin-password",
            internal_webhook_secret="prod-internal-webhook-secret-with-more-than-32-chars",
        )
    )


def test_production_env_rejects_default_internal_webhook_secret():
    with pytest.raises(RuntimeError, match="INTERNAL_WEBHOOK_SECRET uses a known default value"):
        validate_production_safety(
            settings(
                environment="production",
                secret_key="prod-secret-key-with-more-than-32-characters",
                admin_seed_password="not-the-default-admin-password",
                internal_webhook_secret="change-me",
            )
        )


def test_production_env_rejects_empty_internal_webhook_secret():
    with pytest.raises(RuntimeError, match="INTERNAL_WEBHOOK_SECRET must not be empty"):
        validate_production_safety(
            settings(
                environment="production",
                secret_key="prod-secret-key-with-more-than-32-characters",
                admin_seed_password="not-the-default-admin-password",
                internal_webhook_secret="",
            )
        )
