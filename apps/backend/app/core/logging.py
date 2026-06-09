from __future__ import annotations

import json
import logging
from typing import Any


logger = logging.getLogger("smsbridge.requests")


def log_request_completion(
    *,
    request_id: str | None,
    user_id: int | None,
    supplier_id: int | None,
    buyer_api_key_id: int | None,
    endpoint: str,
    method: str,
    status_code: int,
) -> None:
    payload: dict[str, Any] = {
        "event": "request_completed",
        "request_id": request_id,
        "user_id": user_id,
        "supplier_id": supplier_id,
        "buyer_api_key_id": buyer_api_key_id,
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
    }
    logger.info(json.dumps(payload, sort_keys=True, separators=(",", ":")))
