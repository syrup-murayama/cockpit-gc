"""Datetime helpers for task age calculations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def age_days(task: dict[str, Any], now: datetime) -> int | None:
    dt = parse_time(task.get("lastActivityAt") or task.get("createdAt"))
    if dt is None:
        return None
    return max(0, int((now - dt.astimezone(timezone.utc)).total_seconds() // 86400))
