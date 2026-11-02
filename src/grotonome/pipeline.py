"""Relie les books ANJ à la référence sharp et ne propose que l'EV mesurée."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from grotonome.devig import devig, overround
from grotonome.models import FetchReport, Proposal, SharpPrice, SoftPrice
from grotonome.names import normalize, same_team
from grotonome.sources.parse import competition_key
from grotonome.value import combined_overround, expected_value, select_side, stake_fraction

DISAGREE = 0.08


@dataclass
class RunResult:
    proposals: list[Proposal] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)
    reports: list[FetchReport] = field(default_factory=list)
    sharp_snapshots: list[dict] = field(default_factory=list)
    devig: str = "power"
    unmatched: int = 0
    unpriced: int = 0
    shopping: list[dict] = field(default_factory=list)


def analyze(
    reports: list[FetchReport],
    *,
    method: str = "power",
    kelly: float = 0.25,
    cap: float = 0.015,
    min_ev: float = 0.0,
    pricer=None,
    price_limit: int = 25,
) -> RunResult:
    soft = [event for report in reports for event in report.soft]
    sharp = [event for report in reports for event in report.sharp if event.probs or event.odds]
    stubs_by_source: dict[str, list] = {}
    for report in reports:
        for event in report.sharp:
            if event.probs is None and event.odds is None and event.external_id:
                stubs_by_source.setdefault(event.source, []).append(event)
    result = RunResult(reports=list(reports), devig=method)
    if pricer is not None:
        for group in stubs_by_source.values():
            priced, left = _price_matches(soft, group, pricer, price_limit)
            sharp.extend(priced)
            result.unpriced += left
    seen_matches: set[tuple] = set()
    for event in soft:
        refs = [s for s in sharp if _same_match(event, s)]
        key = (event.home, event.away, event.kickoff.isoformat(), event.source)
        if key in seen_matches:
            continue
        seen_matches.add(key)
        if _already_started(event):
            result.skipped.append(
                {
                    "match": f"{event.home} – {event.away}",
                    "bookmaker": event.source,
                    "reason": "coup d'envoi passé",
                }
            )
            continue
        if not refs:
            result.unmatched += 1
            continue
        grouped, sources = _by_source(refs, method)
        if grouped is None:
            result.skipped.append(
                {
                    "match": f"{event.home} – {event.away}",
                    "bookmaker": event.source,
                    "reason": "même référence en désaccord",
                }
            )
            continue
        fairs = grouped
        if not fairs:
            result.unmatched += 1
            continue
        fair, spread = _consensus(fairs)
        result.sharp_snapshots.append(
            {
                "home": event.home,
                "away": event.away,
                "kickoff": event.kickoff.isoformat(),
                "observed_at": event.captured_at.isoformat(),
                "fair_p": fair,
                "sources": sources,
            }
        )
        warnings = []
        if event.movement_at:
            try:
                stale = _as_utc(event.captured_at) - _as_utc(event.movement_at) > timedelta(hours=24)
            except (TypeError, ValueError, OverflowError):
                stale = False
            if stale:
                warnings.append(
                    f"dernier mouvement {event.movement_at.strftime('%Y-%m-%d %H:%M')} UTC"
                )
        if spread > DISAGREE:
            result.skipped.append(
                {
                    "match": f"{event.home} – {event.away}",
                    "bookmaker": event.source,
                    "reason": f"références en désaccord ({spread:.1%})",
                }
            )
            continue
        names = (event.home, "Nul", event.away)
        positive = select_side(event.odds, tuple(fair), min_ev=min_ev)
        if len(positive) > 1:
            warnings.append("plusieurs issues du même match ont une EV positive")
        margin = overround(event.odds)
        for side in positive:
            result.proposals.append(
                Proposal(
                    competition=event.competition,
                    home=event.home,
                    away=event.away,
                    kickoff=event.kickoff,
                    side=side,
                    selection=names[side],
                    bookmaker=event.source,
                    odds=event.odds[side],
                    fair_p=fair[side],
                    ev=expected_value(fair[side], event.odds[side]),
                    stake_fraction=stake_fraction(fair[side], event.odds[side], kelly=kelly, cap=cap),
                    overround=margin,
                    sharp_sources=tuple(dict.fromkeys(sources)),
                    devig=method,
                    warnings=tuple(warnings),
                    movement_at=event.movement_at,
                )
            )
    result.proposals.sort(key=lambda item: item.ev, reverse=True)
    result.shopping = _shopping(soft)
    return result


def _shopping(soft: list[SoftPrice]) -> list[dict]:
    groups: dict[tuple, list[SoftPrice]] = {}
    for event in soft:
        hour = _as_utc(event.kickoff).replace(minute=0, second=0, microsecond=0)
        key = (normalize(event.home), normalize(event.away), hour.isoformat())
        groups.setdefault(key, []).append(event)
    rows = []
    for events in groups.values():
        books = {event.source for event in events}
        if len(books) < 2:
            continue
        # Une cote par bookmaker : la première, sans mélanger deux lignes du même book.
        picked = []
        seen = set()
        for event in events:
            if event.source in seen:
                continue
            seen.add(event.source)
            picked.append(event)
        if len(picked) < 2:
            continue
        margin = combined_overround([event.odds for event in picked])
        rows.append(
            {
                "match": f"{picked[0].home} – {picked[0].away}",
                "books": [event.source for event in picked],
                "margin": margin,
                "surebet": margin < 0,
            }
        )
    rows.sort(key=lambda row: row["margin"])
    return rows[:20]


def _price_matches(
    soft: list[SoftPrice], stubs: list[SharpPrice], pricer, limit: int
) -> tuple[list[SharpPrice], int]:
    wanted = []
    for stub in stubs:
        if any(_same_match(event, stub) for event in soft):
            wanted.append(stub)
    # Le plafond garde les coups d'envoi les plus proches, pas l'ordre du flux.
    wanted.sort(key=lambda item: _as_utc(item.kickoff))
    priced = []
    for stub in wanted[:limit]:
        try:
            quote = pricer(stub)
        except Exception:
            continue
        if quote is not None and (quote.probs or quote.odds):
            priced.append(quote)
    return priced, max(0, len(wanted) - limit)


def _same_match(soft: SoftPrice, sharp: SharpPrice, *, hours: float = 3) -> bool:
    try:
        delta = abs((_as_utc(soft.kickoff) - _as_utc(sharp.kickoff)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return False
    if delta > hours * 3600:
        return False
    if _competition_conflict(soft.competition, sharp.competition):
        return False
    return same_team(soft.home, sharp.home) and same_team(soft.away, sharp.away)


def _competition_conflict(left: str, right: str) -> bool:
    if not right:
        return False
    soft_key = competition_key(left)
    sharp_key = competition_key(right)
    return bool(soft_key and sharp_key and soft_key != sharp_key)


def _already_started(event: SoftPrice) -> bool:
    try:
        return _as_utc(event.kickoff) <= _as_utc(event.captured_at)
    except (TypeError, ValueError, OverflowError):
        return True


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _by_source(refs: list[SharpPrice], method: str) -> tuple[list[list[float]] | None, list[str]]:
    """Une voix par source. Deux cotes Pinnacle ne comptent pas pour deux références."""
    grouped: dict[str, list[list[float]]] = {}
    order: list[str] = []
    for ref in refs:
        try:
            probs = _fair(ref, method)
        except (ValueError, ZeroDivisionError, OverflowError, TypeError, ArithmeticError):
            continue
        grouped.setdefault(ref.source, []).append(probs)
        if ref.source not in order:
            order.append(ref.source)
    fairs: list[list[float]] = []
    sources: list[str] = []
    for source in order:
        group = grouped[source]
        if len(group) >= 2:
            for index in range(3):
                column = [item[index] for item in group]
                if max(column) - min(column) > DISAGREE:
                    return None, []
        avg = [sum(item[index] for item in group) / len(group) for index in range(3)]
        total = sum(avg)
        if total <= 0:
            continue
        fairs.append([value / total for value in avg])
        sources.append(source)
    return fairs, sources


def _fair(ref: SharpPrice, method: str) -> list[float]:
    if ref.probs is not None:
        if len(ref.probs) != 3 or any(p is None or not 0 < p < 1 for p in ref.probs):
            raise ValueError("probabilités sharp inutilisables")
        total = sum(ref.probs)
        # Un carnet incohérent (trois milieux à 0,9) n'est pas une marge de book.
        if not 0.90 <= total <= 1.15:
            raise ValueError("probabilités sharp incohérentes")
        odds = tuple(1.0 / p for p in ref.probs)
        return devig(odds, method)
    if ref.odds is not None:
        return devig(ref.odds, method)
    raise ValueError("référence sans prix")


def _consensus(fairs: list[list[float]]) -> tuple[list[float], float]:
    width = 0.0
    if len(fairs) >= 2:
        for index in range(3):
            column = [fair[index] for fair in fairs]
            width = max(width, max(column) - min(column))
    avg = [sum(fair[index] for fair in fairs) / len(fairs) for index in range(3)]
    total = sum(avg)
    return [value / total for value in avg], width
