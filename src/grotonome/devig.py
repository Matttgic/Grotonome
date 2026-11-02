"""Retrait de la marge d'un marché à cotes décimales.

Les probabilités implicites brutes 1/cote somment à plus de 1. La marge est
cette somme moins 1. Quatre méthodes renvoient des probabilités qui somment à 1.

- proportionnelle : chaque cote est réduite du même facteur ;
- puissance : on cherche n tel que la somme des (1/cote)^n vaille 1 ;
- additive : on retire la même quantité à chaque probabilité implicite
  (peut devenir négative, alors la méthode est refusée) ;
- Shin : part d'initiés z choisie pour que les probabilités somment à 1.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

METHODS = ("power", "multiplicative", "shin", "additive")


def implied(odds: Sequence[float]) -> list[float]:
    _check(odds)
    return [1.0 / o for o in odds]


def overround(odds: Sequence[float]) -> float:
    return sum(implied(odds)) - 1.0


def multiplicative(odds: Sequence[float]) -> list[float]:
    qs = implied(odds)
    total = sum(qs)
    return [q / total for q in qs]


def additive(odds: Sequence[float]) -> list[float]:
    qs = implied(odds)
    excess = sum(qs) - 1.0
    share = excess / len(qs)
    probs = [q - share for q in qs]
    if any(p <= 0 for p in probs):
        raise ValueError("méthode additive négative sur ce marché")
    total = sum(probs)
    return [p / total for p in probs]


def power(odds: Sequence[float]) -> list[float]:
    qs = implied(odds)
    total = sum(qs)
    if total <= 1.0:
        return [q / total for q in qs]

    def score(n: float) -> float:
        return sum(q**n for q in qs)

    lo, hi = 0.5, 1.5
    while score(hi) > 1.0 and hi < 40:
        hi *= 1.5
    for _ in range(80):
        mid = (lo + hi) / 2
        if score(mid) > 1.0:
            lo = mid
        else:
            hi = mid
    n = (lo + hi) / 2
    probs = [q**n for q in qs]
    scale = sum(probs)
    return [p / scale for p in probs]


def shin(odds: Sequence[float]) -> list[float]:
    """Méthode de Shin (1992/1993), résolution de z par dichotomie."""
    qs = implied(odds)
    if sum(qs) <= 1.0:
        total = sum(qs)
        return [q / total for q in qs]

    def probs(z: float) -> list[float]:
        if z <= 0:
            return list(qs)
        out = []
        for q in qs:
            disc = z * z + 4 * (1 - z) * q * q
            out.append((math.sqrt(disc) - z) / (2 * (1 - z)))
        return out

    lo, hi = 0.0, 0.5
    for _ in range(80):
        mid = (lo + hi) / 2
        if sum(probs(mid)) > 1.0:
            lo = mid
        else:
            hi = mid
    found = probs((lo + hi) / 2)
    scale = sum(found)
    return [p / scale for p in found]


def devig(odds: Sequence[float], method: str = "power") -> list[float]:
    if method == "power":
        return power(odds)
    if method == "multiplicative":
        return multiplicative(odds)
    if method == "shin":
        return shin(odds)
    if method == "additive":
        return additive(odds)
    raise ValueError(f"méthode inconnue : {method}")


def _check(odds: Sequence[float]) -> None:
    if len(odds) < 2:
        raise ValueError("au moins deux issues")
    for o in odds:
        if o is None or not math.isfinite(o) or o <= 1.0:
            raise ValueError(f"cote invalide : {o}")
