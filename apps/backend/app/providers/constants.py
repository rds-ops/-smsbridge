from __future__ import annotations

ALLOWED_PROVIDER_TYPES = ("mock", "supplier_pool", "five_sim", "sms_activate", "sms_man")
ALLOWED_PROVIDER_STATUSES = ("active", "inactive", "disabled")

PROVIDER_TYPE_PATTERN = "^(mock|supplier_pool|five_sim|sms_activate|sms_man)$"
PROVIDER_STATUS_PATTERN = "^(active|inactive|disabled)$"
