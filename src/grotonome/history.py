"""Historique horodaté des cotes. Sert à mesurer une CLV plus tard, pas à l'inventer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from grotonome.devig import devig, normalize_probs
from grotonome.models import FetchReport, SharpPrice, SoftPrice
from grotonome.names import normalize


def snapshot_rows(reports: list[FetchReport], sharp: list[SharpPrice]) -> list[dict]:
    rows = []
    for report in reports:
        for event in report.soft:
            rows.append(_row(event, kind="book"))
    seen = set()
    for event in sharp:
        if event.odds is None and event.probs is None:
            continue
        key = (event.source, event.external_id, event.home, event.away, event.kickoff.isoformat())
        if key in seen:
            continue
        seen.add(key)
        rows.append(_row(event, kind="sharp"))
    return rows


def append_rows(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def french_clv(rows: list[dict]) -> dict:
    """CLV d'une cote française face à une référence sharp strictement plus tardive, avant le coup d'envoi."""
    books = [row for row in rows if row.get("kind") == "book" and row.get("odds")]
    sharps = [row for row in rows if row.get("kind") == "sharp" and (row.get("probs") or row.get("odds"))]
    values = []
    for book in books:
        later = []
        for sharp in sharps:
            if not _same(book, sharp):
                continue
            if not (book["at"] < sharp["at"] < book["kickoff"]):
                continue
            fair = _fair_row(sharp)
            if fair is None:
                continue
            later.append((sharp["at"], fair))
        if not later:
            continue
        _at, fair = max(later)
        # L'issue retenue est celle qui avait l'EV la plus haute face à CETTE clôture,
        # ce qui mesure le meilleur écart réalisé, pas un choix fait à l'ouverture.
        # Pour éviter cette fuite, on fige l'issue qui était la meilleure face à la
        # première référence contemporaine ou antérieure. S'il n'y en a pas, on ne calcule pas.
        opening = []
        for sharp in sharps:
            if not _same(book, sharp):
                continue
            if sharp["at"] > book["at"]:
                continue
            fair_open = _fair_row(sharp)
            if fair_open is None:
                continue
            opening.append((sharp["at"], fair_open))
        if not opening:
            continue
        _opened, fair_open = max(opening)
        side = max(range(3), key=lambda index: fair_open[index] * book["odds"][index] - 1)
        if fair_open[side] * book["odds"][side] - 1 <= 0:
            continue
        values.append(book["odds"][side] * fair[side] - 1)
    return {"n": len(values), "clv_mean": (sum(values) / len(values)) if values else None}


def _fair_row(row: dict) -> list[float] | None:
    try:
        if row.get("probs"):
            return normalize_probs(row["probs"])
        if row.get("odds"):
            return devig(row["odds"], "power")
    except (ValueError, ZeroDivisionError, TypeError):
        return None
    return None


def _same(book: dict, sharp: dict) -> bool:
    if normalize(book.get("home") or "") != normalize(sharp.get("home") or ""):
        return False
    if normalize(book.get("away") or "") != normalize(sharp.get("away") or ""):
        return False
    try:
        left = datetime.fromisoformat(book["kickoff"])
        right = datetime.fromisoformat(sharp["kickoff"])
    except (KeyError, ValueError):
        return False
    if left.tzinfo is None:
        left = left.replace(tzinfo=timezone.utc)
    if right.tzinfo is None:
        right = right.replace(tzinfo=timezone.utc)
    return abs((left - right).total_seconds()) <= 3 * 3600


def _row(event: SoftPrice | SharpPrice, *, kind: str) -> dict:
    body = {
        "at": event.captured_at.astimezone(timezone.utc).isoformat(),
        "kind": kind,
        "source": event.source,
        "competition": event.competition,
        "home": event.home,
        "away": event.away,
        "kickoff": event.kickoff.astimezone(timezone.utc).isoformat(),
        "odds": list(event.odds) if event.odds else None,
        "probs": list(event.probs) if getattr(event, "probs", None) else None,
    }
    movement = getattr(event, "movement_at", None)
    if movement is not None:
        body["movement_at"] = movement.astimezone(timezone.utc).isoformat()
    return body
