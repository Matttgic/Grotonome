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


def _csv_header_ok(text: str) -> bool:
    lines = text.lstrip("\ufeff").splitlines()
    if not lines:
        return False
    header = [cell.strip() for cell in lines[0].split(",")]
    return "FTR" in header


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
                text = _cached_csv(target)
                if text is None:
                    downloaded = get_text(url, timeout=30)
                    if not _csv_header_ok(downloaded):
                        notes.append(f"{division} {code}: réponse non CSV")
                        if target.exists():
                            target.unlink()
                        continue
                    target.write_text(downloaded, encoding="utf-8")
                    text = downloaded
                found.extend(parse_results_csv(text))
                notes.append(f"{division} {code}: ok")
            except HttpError as exc:
                notes.append(f"{division} {code}: HTTP {exc.status}")
            except OSError:
                notes.append(f"{division} {code}: illisible")
    return found, "; ".join(notes)


def _cached_csv(target: Path) -> str | None:
    if not target.exists() or target.stat().st_size < 50:
        return None
    text = target.read_text(encoding="utf-8")
    if _csv_header_ok(text):
        return text
    return None


def _date(text: str) -> date | None:
    text = text.strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None
