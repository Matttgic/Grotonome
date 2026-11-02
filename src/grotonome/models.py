"""Objets échangés entre les sources et le calcul. Pas de cote par défaut."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class SoftPrice:
    source: str
    competition: str
    home: str
    away: str
    kickoff: datetime
    odds: tuple[float, float, float]
    captured_at: datetime
    movement_at: datetime | None = None


@dataclass(frozen=True)
class SharpPrice:
    """Référence. `probs` = milieux de fourchette (pas encore normalisés).
    `odds` = cotes décimales d'un book sharp, marge encore incluse.
    """

    source: str
    competition: str
    home: str
    away: str
    kickoff: datetime
    captured_at: datetime
    probs: tuple[float, float, float] | None = None
    odds: tuple[float, float, float] | None = None
    external_id: str | None = None


@dataclass
class FetchReport:
    source: str
    kind: str
    ok: bool
    detail: str
    elapsed_s: float
    n: int = 0
    soft: list[SoftPrice] = field(default_factory=list)
    sharp: list[SharpPrice] = field(default_factory=list)


@dataclass(frozen=True)
class Proposal:
    competition: str
    home: str
    away: str
    kickoff: datetime
    side: int
    selection: str
    bookmaker: str
    odds: float
    fair_p: float
    ev: float
    stake_fraction: float
    overround: float
    sharp_sources: tuple[str, ...]
    devig: str
    warnings: tuple[str, ...] = ()
    movement_at: datetime | None = None
