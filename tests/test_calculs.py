"""Cas calculés à la main : marge, EV, mise, CLV, intervalle."""

import math

import pytest

from grotonome.devig import additive, multiplicative, overround, power, shin
from grotonome.metrics import mean_interval, unit_pnl
from grotonome.value import (
    closing_value,
    combined_overround,
    expected_value,
    kelly_fraction,
    select_side,
    stake_fraction,
)


def test_proportionnel_a_la_main():
    # Cotes 2, 3 et 5.
    # Implicites : 1/2 = 0,5 ; 1/3 ; 1/5 = 0,2.
    # Somme = 0,5 + 0,3333333333 + 0,2 = 1,0333333333.
    # Proportionnel : 0,5 / 1,0333333333 = 0,4838709677.
    odds = (2, 3, 5)
    assert overround(odds) == pytest.approx(1 / 30)
    probs = multiplicative(odds)
    assert probs[0] == pytest.approx(0.5 / (31 / 30))
    assert probs[1] == pytest.approx((1 / 3) / (31 / 30))
    assert probs[2] == pytest.approx(0.2 / (31 / 30))
    assert sum(probs) == pytest.approx(1)


def test_puissance_figee():
    probs = power((2, 3, 5))
    assert probs == pytest.approx((0.48875648, 0.32153134, 0.18971218), abs=1e-6)
    assert sum(probs) == pytest.approx(1)
    # Le favori reçoit une part plus grande qu'en proportionnel.
    assert probs[0] > multiplicative((2, 3, 5))[0]


def test_marche_symetrique():
    for method in (multiplicative, power, shin):
        assert method((1.9, 1.9)) == pytest.approx((0.5, 0.5))


def test_shin_favori_au_dessus_du_proportionnel():
    odds = (1.4, 4.5, 8.0)
    assert shin(odds)[0] > multiplicative(odds)[0]
    assert sum(shin(odds)) == pytest.approx(1)


def test_additive_retrait_egal():
    # Implicites 0,6 et 0,6, somme 1,2, retrait 0,1 chacune → 0,5 / 0,5.
    assert additive((1 / 0.6, 1 / 0.6)) == pytest.approx((0.5, 0.5))


def test_additive_refuse_un_negatif():
    # 1,20 / 1,20 / 20 : la marge est trop large pour l'outsider.
    with pytest.raises(ValueError):
        additive((1.2, 1.2, 20))


def test_ev_et_kelly_a_la_main():
    # p = 0,40, cote = 2,70.
    # EV = 0,40 × 2,70 − 1 = 0,08.
    # Kelly = 0,08 / (2,70 − 1) = 0,08 / 1,70 = 0,0470588235.
    # Quart de Kelly = 0,0117647059. Sur 1 000 € : 11,76 €.
    assert expected_value(0.40, 2.70) == pytest.approx(0.08)
    assert kelly_fraction(0.40, 2.70) == pytest.approx(0.08 / 1.70)
    assert stake_fraction(0.40, 2.70) == pytest.approx(0.25 * 0.08 / 1.70)
    assert stake_fraction(0.40, 2.70) * 1000 == pytest.approx(11.764705882, abs=1e-6)


def test_kelly_nul_si_ev_negative_et_plafond():
    assert kelly_fraction(0.40, 2.0) == 0
    # p = 0,80, cote 1,50. EV = 0,20. Kelly = 0,20 / 0,50 = 0,40.
    # Quart = 0,10, plafonné à 1,5 %.
    assert expected_value(0.80, 1.50) == pytest.approx(0.20)
    assert stake_fraction(0.80, 1.50, kelly=0.25, cap=0.015) == pytest.approx(0.015)


def test_clv_a_la_main():
    # Cote prise 2,10, probabilité juste de clôture 0,50 → EV de clôture 0,05.
    assert closing_value(2.10, 0.50) == pytest.approx(0.05)


def test_pnl_unitaire():
    assert unit_pnl(2.50, True) == pytest.approx(1.50)
    assert unit_pnl(2.50, False) == -1


def test_intervalle_connu():
    # Profits 1, −1, 1, −1. Moyenne 0.
    # Variance = 4/3, écart-type de la moyenne = sqrt(1/3).
    # Demi-largeur 1,96 × sqrt(1/3).
    stats = mean_interval([1, -1, 1, -1])
    assert stats.mean == pytest.approx(0)
    assert stats.low == pytest.approx(-1.96 * math.sqrt(1 / 3))
    assert stats.high == pytest.approx(1.96 * math.sqrt(1 / 3))
    assert mean_interval([1.0]).low is None
    assert mean_interval([]).mean is None


def test_surebet_a_la_main():
    # Meilleure cote de chaque issue : 2,20, 3,60 et 4,20.
    # 1/2,20 + 1/3,60 + 1/4,20 = 0,454545 + 0,277778 + 0,238095 = 0,970418.
    # Marge = −0,029582, donc surebet d'environ 2,96 %.
    margin = combined_overround([(2.2, 3.4, 3.2), (2.0, 3.6, 4.2)])
    assert margin == pytest.approx(1 / 2.2 + 1 / 3.6 + 1 / 4.2 - 1)
    assert margin < 0


def test_selection_ignore_la_cloture():
    # La fonction n'accepte pas la clôture : seulement cote et probabilité du moment.
    picked = select_side((2.30, 3.20, 4.50), (0.45, 0.30, 0.25))
    # Domicile : 0,45×2,30−1 = 0,035. Nul : 0,30×3,20−1 = −0,04. Extérieur : 0,125.
    assert picked == [0, 2]
    assert select_side((2.0, 3.0, 4.0), (0.45, 0.30, 0.25)) == []
