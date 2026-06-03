"""Mock notification dispatcher.

In production these methods would call SendGrid / APNs / FCM / a websocket hub.
Here they push a structured JSON event onto a Redis pub/sub channel and a capped
list, so the frontend (or a test) can observe delivered notifications without
any third-party credentials.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from app.core.redis_client import get_redis

logger = logging.getLogger("alphapulse.notifications")

NOTIFICATION_CHANNEL = "alphapulse:notifications"
_INBOX_KEY_TPL = "notifications:inbox:{user_id}"
_INBOX_MAX = 100


async def dispatch(user_id: str, kind: str, payload: dict[str, Any]) -> None:
    """Deliver a single notification to a user (mock transport)."""
    redis = get_redis()
    event = {
        "user_id": user_id,
        "kind": kind,
        "payload": payload,
        "delivered_at": datetime.now(timezone.utc).isoformat(),
    }
    serialized = json.dumps(event)

    pipe = redis.pipeline()
    pipe.publish(NOTIFICATION_CHANNEL, serialized)
    inbox = _INBOX_KEY_TPL.format(user_id=user_id)
    pipe.lpush(inbox, serialized)
    pipe.ltrim(inbox, 0, _INBOX_MAX - 1)
    await pipe.execute()

    logger.info("notification → user=%s kind=%s payload=%s", user_id, kind, payload)
