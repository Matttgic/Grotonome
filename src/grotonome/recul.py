"""Recul après 403 ou 429. On attend, on ne change pas d'identité ni de réseau."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

# 15 min, puis 30, 60, et plafond 120. Le passage suivant reste à 6 min pour les autres sources.
_STEPS_MINUTES = (15, 30, 60, 120)


def backoff_delay(failures: int) -> timedelta:
    if failures <= 0:
        return timedelta(0)
    index = min(failures, len(_STEPS_MINUTES)) - 1
    return timedelta(minutes=_STEPS_MINUTES[index])


def http_status(detail: str) -> int | None:
    match = re.search(r"HTTP (\d{3})", detail or "")
    if not match:
        return None
    return int(match.group(1))


def blocked_until(state: dict, source: str, now: datetime) -> datetime | None:
    entry = state.get(source) or {}
    raw = entry.get("until")
    if not raw:
        return None
    try:
        until = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if until.tzinfo is None and now.tzinfo is not None:
        until = until.replace(tzinfo=now.tzinfo)
    if until > now:
        return until
    return None


def observe(state: dict, source: str, *, ok: bool, detail: str, now: datetime) -> None:
    status = http_status(detail)
    if ok or status not in {403, 429}:
        if ok:
            state.pop(source, None)
        return
    failures = int((state.get(source) or {}).get("fails") or 0) + 1
    until = now + backoff_delay(failures)
    state[source] = {"fails": failures, "until": until.isoformat(), "status": status}
