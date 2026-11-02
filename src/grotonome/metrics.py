"""ROI, CLV et intervalle de confiance. Rien n'est inventé si n est trop petit."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class MeanInterval:
    n: int
    mean: float | None
    low: float | None
    high: float | None

    @property
    def available(self) -> bool:
        return self.mean is not None and self.low is not None


def mean_interval(values: list[float], *, z: float = 1.96) -> MeanInterval:
    """Moyenne et intervalle normal à 95 %. Indisponible s'il y a moins de 2 valeurs."""
    n = len(values)
    if n == 0:
        return MeanInterval(0, None, None, None)
    mean = sum(values) / n
    if n < 2:
        return MeanInterval(n, mean, None, None)
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    # Trois pertes identiques donnent un écart-type nul : l'intervalle ne doit pas
    # se refermer sur le point, comme si le résultat était certain.
    if var == 0:
        return MeanInterval(n, mean, None, None)
    se = math.sqrt(var / n)
    return MeanInterval(n, mean, mean - z * se, mean + z * se)


def clustered_mean_interval(groups: list[list[float]], *, z: float = 1.96) -> MeanInterval:
    """Moyenne de tous les paris, intervalle robuste au regroupement par match.

    Deux mises sur le même match ne comptent pas comme deux observations
    indépendantes. Avec un seul match, ou une variance nulle, l'intervalle
    reste absent.
    """
    values = [value for group in groups for value in group]
    n = len(values)
    if n == 0:
        return MeanInterval(0, None, None, None)
    mean = sum(values) / n
    if n < 2 or len(groups) < 2:
        return MeanInterval(n, mean, None, None)
    if all(value == values[0] for value in values):
        return MeanInterval(n, mean, None, None)
    scores = [sum(value - mean for value in group) for group in groups]
    g = len(groups)
    variance = (g / (g - 1)) * sum(score * score for score in scores) / (n * n)
    se = math.sqrt(variance)
    if se == 0:
        return MeanInterval(n, mean, None, None)
    return MeanInterval(n, mean, mean - z * se, mean + z * se)


def unit_pnl(odds: float, won: bool) -> float:
    """Profit d'une mise de 1. La mise est rendue en cas de gain, donc cote − 1."""
    if odds <= 1:
        raise ValueError("cote invalide")
    return (odds - 1.0) if won else -1.0
