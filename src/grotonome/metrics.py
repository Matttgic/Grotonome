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
    se = math.sqrt(var / n)
    return MeanInterval(n, mean, mean - z * se, mean + z * se)


def unit_pnl(odds: float, won: bool) -> float:
    """Profit d'une mise de 1. La mise est rendue en cas de gain, donc cote − 1."""
    if odds <= 1:
        raise ValueError("cote invalide")
    return (odds - 1.0) if won else -1.0
