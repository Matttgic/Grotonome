"""Espérance, mise et valeur d'un pari contre une probabilité juste."""

from __future__ import annotations


def expected_value(probability: float, odds: float) -> float:
    """EV unitaire : probabilité × cote − 1. Négatif si la cote est trop basse."""
    if not 0 < probability < 1:
        raise ValueError("probabilité hors de (0, 1)")
    if odds <= 1:
        raise ValueError("cote invalide")
    return probability * odds - 1.0


def kelly_fraction(probability: float, odds: float) -> float:
    """Fraction de bankroll de Kelly. 0 si l'espérance n'est pas positive."""
    ev = expected_value(probability, odds)
    if ev <= 0:
        return 0.0
    return ev / (odds - 1.0)


def stake_fraction(
    probability: float,
    odds: float,
    *,
    kelly: float = 0.25,
    cap: float = 0.015,
) -> float:
    """Mise conseillée en fraction de bankroll (Kelly fractionné, plafonné)."""
    if kelly < 0 or cap < 0:
        raise ValueError("kelly et plafond doivent être positifs")
    raw = kelly_fraction(probability, odds) * kelly
    return min(cap, raw)


def closing_value(odds_taken: float, closing_probability: float) -> float:
    """EV du pari face à la probabilité juste de clôture. C'est la CLV retenue."""
    return expected_value(closing_probability, odds_taken)


def combined_overround(markets: list[tuple[float, float, float]]) -> float:
    """Marge du meilleur prix de chaque issue. Négative : surebet."""
    if not markets:
        raise ValueError("aucun marché")
    best = [max(market[index] for market in markets) for index in range(3)]
    if any(odds <= 1 for odds in best):
        raise ValueError("cote invalide")
    return sum(1.0 / odds for odds in best) - 1.0


def select_side(
    soft_odds: tuple[float, float, float],
    fair: tuple[float, float, float],
    *,
    min_ev: float = 0.0,
) -> list[int]:
    """Indices des issues à EV strictement positive et au moins égale au seuil."""
    if len(soft_odds) != 3 or len(fair) != 3:
        raise ValueError("marché 1N2 à trois issues")
    picked = []
    for i, (odds, prob) in enumerate(zip(soft_odds, fair, strict=True)):
        if odds <= 1 or not 0 < prob < 1:
            continue
        ev = expected_value(prob, odds)
        if ev <= 0:
            continue
        if ev < min_ev:
            continue
        picked.append(i)
    return picked
