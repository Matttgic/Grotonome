"""Fraîcheur des cotes Betclic lues sur SportyTrader.

Le site betclic.fr répond 403. La liste utilise la page publique SportyTrader.
Tant qu'un retard médian n'est pas mesuré sur au moins 8 suivis, une cote
Betclic identique à la précédente sort de la liste si la probabilité juste
a bougé d'au moins 2 points depuis l'ancre enregistrée au dernier changement
de cette cote. Deux points, c'est quatre fois le seuil d'enregistrement des
probabilités (0,005) : un déplacement net, pas un tick.

Le cache Cloudflare de SportyTrader annonce ``s-maxage=600`` (2 novembre 2026,
03:59 UTC). Ce n'est pas un retard mesuré face à Betclic. La page ne donne ni
``Age``, ni ``Last-Modified``, ni heure de mise à jour.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone

from grotonome.history import quote_key
from grotonome.models import SoftPrice
from grotonome.names import same_team

SHARP_MOVE = 0.02
MIN_LAG_SAMPLE = 8
ODDS_TICK = 0.01
PROBS_TICK = 0.005
RELAY_WARNING = "cote relayée, à vérifier dans l'appli Betclic"
STALE_REASON = "cote Betclic figée, sharp bougé d'au moins 2 points"

SHARP_SOURCES = frozenset({"pinnacle", "smarkets", "matchbook"})
BOOK_SOURCES = frozenset({"unibet", "winamax", "pmu"})


def betclic_key(home: str, away: str, kickoff: str) -> str:
    return quote_key(
        {
            "kind": "book",
            "source": "betclic",
            "home": home,
            "away": away,
            "kickoff": kickoff,
        }
    )


def prior_betclic(prior: dict | None, event: SoftPrice) -> dict | None:
    if not prior or event.source != "betclic":
        return None
    kickoff = event.kickoff.astimezone(timezone.utc).isoformat()
    found = prior.get(betclic_key(event.home, event.away, kickoff))
    return found if isinstance(found, dict) else None


def betclic_frozen(odds: tuple[float, float, float], fair: list[float], entry: dict | None) -> bool:
    """Vrai si la cote Betclic n'a pas bougé depuis l'ancre et que le sharp a bougé d'au moins 2 points."""
    if not entry or entry.get("fair") is None or entry.get("odds") is None:
        return False
    old_odds = entry["odds"]
    old_fair = entry["fair"]
    if len(old_odds) != 3 or len(old_fair) != 3 or len(fair) != 3:
        return False
    if any(abs(float(a) - float(b)) >= ODDS_TICK for a, b in zip(old_odds, odds)):
        return False
    gap = max(abs(float(a) - float(b)) for a, b in zip(old_fair, fair))
    return gap >= SHARP_MOVE


def remember_betclic_fair(etat: dict, anchors: list[dict], deltas: list[dict]) -> None:
    """Pose la probabilité juste sur la cote Betclic quand cette cote change.

    Si la cote est inchangée, l'ancre reste celle du dernier changement.
    """
    changed = {quote_key(row) for row in deltas}
    for mark in anchors:
        key = betclic_key(mark["home"], mark["away"], mark["kickoff"])
        entry = etat.get(key)
        if not isinstance(entry, dict):
            continue
        if key in changed or entry.get("fair") is None:
            entry["fair"] = [float(p) for p in mark["fair"]]


def measure_lag(rows: list[dict]) -> dict:
    """Délai entre un mouvement (sharp, ou Unibet / Winamax / PMU) et le suivi Betclic.

    Un suivi exige une cote Betclic déjà vue au moment du mouvement, puis une
    cote Betclic différente ensuite. Sans cote antérieure, le mouvement est
    absent. Sans changement ensuite, il est censuré et ne entre pas dans le médian.
    """
    sharp = _summarize(_delays(rows, SHARP_SOURCES, "sharp"))
    books = _summarize(_delays(rows, BOOK_SOURCES, "book"))
    per_book = {
        source: _summarize(_delays(rows, frozenset({source}), "book"))
        for source in sorted(BOOK_SOURCES)
    }
    return {
        "n_rows": len(rows),
        "n_betclic": sum(1 for row in rows if row.get("source") == "betclic" and row.get("kind") == "book"),
        "sharp": sharp,
        "books": books,
        "per_book": per_book,
        "min_sample": MIN_LAG_SAMPLE,
        "too_small": sharp["n_followed"] < MIN_LAG_SAMPLE,
    }


def _delays(rows: list[dict], sources: frozenset[str], kind: str) -> tuple[list[float], int, int, int]:
    triggers = _movements(rows, kind, sources)
    betclic = _series(rows, "book", frozenset({"betclic"}))
    delays: list[float] = []
    censored = 0
    absent = 0
    for trigger in triggers:
        delay = _follow(trigger, betclic)
        if delay is None:
            absent += 1
        elif delay == "censored":
            censored += 1
        else:
            delays.append(delay)
    return delays, censored, absent, len(triggers)


def _summarize(parts: tuple[list[float], int, int, int]) -> dict:
    delays, censored, absent, n_moves = parts
    return {
        "n_moves": n_moves,
        "n_followed": len(delays),
        "n_censored": censored,
        "n_absent": absent,
        "median_s": statistics.median(delays) if delays else None,
    }


def _movements(rows: list[dict], kind: str, sources: frozenset[str]) -> list[dict]:
    found = []
    for series in _series(rows, kind, sources):
        for previous, current in zip(series, series[1:]):
            if _moved(previous, current):
                found.append(current)
    return found


def _series(rows: list[dict], kind: str, sources: frozenset[str]) -> list[list[dict]]:
    buckets: dict[tuple, list[dict]] = {}
    for row in rows:
        if row.get("kind") != kind or row.get("source") not in sources:
            continue
        if kind == "book" and not row.get("odds"):
            continue
        if kind == "sharp" and not (row.get("probs") or row.get("odds")):
            continue
        if not row.get("at"):
            continue
        key = (row.get("source"), row.get("home"), row.get("away"), row.get("kickoff"))
        buckets.setdefault(key, []).append(row)
    series = []
    for items in buckets.values():
        items.sort(key=lambda item: item["at"])
        series.append(items)
    return series


def _follow(trigger: dict, series_list: list[list[dict]]):
    candidates = [series for series in series_list if _same_match(trigger, series[0])]
    if not candidates:
        return None
    candidates.sort(key=lambda series: _kickoff_gap(trigger, series[0]))
    series = candidates[0]
    prior = [row for row in series if row["at"] <= trigger["at"]]
    if not prior:
        return None
    baseline = prior[-1]
    for row in series:
        if row["at"] <= trigger["at"]:
            continue
        if _moved(baseline, row):
            return _seconds(trigger["at"], row["at"])
    return "censored"


def _same_match(left: dict, right: dict) -> bool:
    if not same_team(str(left.get("home") or ""), str(right.get("home") or "")):
        return False
    if not same_team(str(left.get("away") or ""), str(right.get("away") or "")):
        return False
    return _kickoff_gap(left, right) <= 3 * 3600


def _kickoff_gap(left: dict, right: dict) -> float:
    try:
        a = _parse(left["kickoff"])
        b = _parse(right["kickoff"])
    except (KeyError, ValueError):
        return 10**9
    return abs((a - b).total_seconds())


def _moved(previous: dict, current: dict) -> bool:
    if _tick(previous.get("odds"), current.get("odds"), ODDS_TICK):
        return True
    if _tick(previous.get("probs"), current.get("probs"), PROBS_TICK):
        return True
    return False


def _tick(old, new, tolerance: float) -> bool:
    if not old or not new or len(old) != len(new):
        return False
    return any(abs(float(a) - float(b)) >= tolerance for a, b in zip(old, new))


def _seconds(start: str, end: str) -> float:
    return (_parse(end) - _parse(start)).total_seconds()


def _parse(value: str) -> datetime:
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)
