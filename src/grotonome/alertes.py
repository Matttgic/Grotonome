"""Alerte immédiate, sans répéter la même offre."""

from __future__ import annotations

from datetime import timezone

from grotonome.models import Proposal
from grotonome.names import normalize


def offer_key(item: Proposal) -> str:
    moment = item.kickoff if item.kickoff.tzinfo else item.kickoff.replace(tzinfo=timezone.utc)
    day = moment.astimezone(timezone.utc).date().isoformat()
    return "|".join(
        [
            item.bookmaker,
            normalize(item.home),
            normalize(item.away),
            day,
            str(item.side),
        ]
    )


def odds_rose(previous: float | None, new: float) -> bool:
    """Vrai seulement si la cote monte d'au moins 0,05 et d'au moins 3 %."""
    if previous is None:
        return True
    if new <= previous:
        return False
    return new >= previous + 0.05 and new >= previous * 1.03


def select_alerts(proposals: list[Proposal], memory: dict) -> list[Proposal]:
    """Ne modifie pas `memory`. L'appelant n'enregistre qu'après un envoi réussi."""
    chosen = []
    for item in proposals:
        key = offer_key(item)
        previous = memory.get(key)
        if isinstance(previous, dict):
            previous = previous.get("odds")
        if not odds_rose(None if previous is None else float(previous), item.odds):
            continue
        chosen.append(item)
    return chosen


def remember_alerts(memory: dict, proposals: list[Proposal]) -> None:
    for item in proposals:
        memory[offer_key(item)] = item.odds
