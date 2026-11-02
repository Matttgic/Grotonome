"""Règlement des paris à partir des CSV football-data.co.uk. Téléchargement facultatif."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from pathlib import Path

from grotonome.http import HttpError, get_text

DIVISIONS = ("E0", "F1", "SP1", "I1", "D1")


def season_code(day: date) -> str:
    start = day.year if day.month >= 7 else day.year - 1
    return f"{start % 100:02d}{(start + 1) % 100:02d}"


def parse_results_csv(text: str) -> list[dict]:
    rows = []
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not reader.fieldnames or "FTR" not in reader.fieldnames:
        return rows
    for row in reader:
        result = (row.get("FTR") or "").strip()
        if result not in {"H", "D", "A"}:
            continue
        parsed = _date(row.get("Date") or "")
        home, away = row.get("HomeTeam"), row.get("AwayTeam")
        if not parsed or not home or not away:
            continue
        rows.append({"home": home, "away": away, "date": parsed.isoformat(), "result": result})
    return rows


def fetch_results(cache: Path, *, day: date) -> tuple[list[dict], str]:
    cache.mkdir(parents=True, exist_ok=True)
    seasons = {season_code(day)}
    # La saison précédente règle les paris encore ouverts autour de la coupure.
    previous = date(day.year - 1, day.month, min(day.day, 28))
    seasons.add(season_code(previous))
    found: list[dict] = []
    notes = []
    for code in sorted(seasons):
        for division in DIVISIONS:
            target = cache / f"{division}_{code}.csv"
            url = f"https://www.football-data.co.uk/mmz4281/{code}/{division}.csv"
            try:
                if not target.exists() or target.stat().st_size < 50:
                    target.write_text(get_text(url, timeout=30), encoding="utf-8")
                found.extend(parse_results_csv(target.read_text(encoding="utf-8")))
                notes.append(f"{division} {code}: ok")
            except HttpError as exc:
                notes.append(f"{division} {code}: HTTP {exc.status}")
            except OSError:
                notes.append(f"{division} {code}: illisible")
    return found, "; ".join(notes)


def _date(text: str) -> date | None:
    text = text.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None
