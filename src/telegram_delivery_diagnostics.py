"""Structured Telegram transport diagnostics shared by publication code."""
from __future__ import annotations

import os

GUARD_REASON_ENV = "AI_RADAR_PUBLICATION_GUARD_REASON"


def record_transport_failure(status_code: int | None, description: str = "") -> str:
    code = int(status_code or 0)
    if code == 429:
        reason = "telegram_rate_limited"
    elif 500 <= code <= 599:
        reason = f"telegram_http_{code}"
    elif code in {401, 403}:
        reason = "telegram_auth_or_permission_denied"
    elif code == 400:
        reason = "telegram_bad_request"
    elif code == 404:
        reason = "telegram_endpoint_or_destination_not_found"
    else:
        reason = "telegram_delivery_failed"
    os.environ[GUARD_REASON_ENV] = reason
    safe_description = " ".join(str(description or "").split())[:300]
    print(f"[Telegram Delivery] FAILED reason={reason} http_status={code} description={safe_description}", flush=True)
    return reason
