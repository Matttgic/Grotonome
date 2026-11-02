"""Décisions de la deuxième passe, avec les chiffres qui les justifient."""

from datetime import datetime, timezone

import pytest

from grotonome.devig import normalize_probs, power
from grotonome.history import french_clv
from grotonome.journal import settle
from grotonome.models import Proposal
from grotonome.names import same_team
from grotonome.pipeline import _fair
from grotonome.models import SharpPrice
from grotonome.sources.parse import parse_smarkets_quotes, parse_unibet_page, parse_winamax_html

NOW = datetime(2026, 11, 2, 1, 15, tzinfo=timezone.utc)
KICK = datetime(2026, 11, 2, 19, 45, tzinfo=timezone.utc)


def test_milieux_normalises_pas_en_puissance():
    # Somme 1,08. Le favori à 0,50.
    raw = (0.50, 0.29, 0.29)
    assert sum(raw) == 1.08
    normalized = normalize_probs(raw)
    powered = power(tuple(1 / p for p in raw))
    # Mesuré : 47,36 % en puissance contre 46,30 % en normalisation, soit 1,06 point.
    assert normalized[0] == 0.50 / 1.08
    assert abs(powered[0] - normalized[0]) == pytest.approx(0.01062083, abs=1e-5)
    fair = _fair(SharpPrice("smarkets", "", "A", "B", KICK, NOW, probs=raw), "power")
    assert fair[0] == normalized[0]


def test_smarkets_sans_liquidite():
    contracts = [
        {"id": "1", "contract_type": {"name": "HOME"}},
        {"id": "2", "contract_type": {"name": "DRAW"}},
        {"id": "3", "contract_type": {"name": "AWAY"}},
    ]
    thin = {"bids": [{"price": 3900, "quantity": 1000}], "offers": [{"price": 4100, "quantity": 1000}]}
    quotes = {"1": thin, "2": thin, "3": thin}
    assert (
        parse_smarkets_quotes(
            event_name="A vs B",
            kickoff=KICK,
            contracts=contracts,
            quotes=quotes,
            captured_at=NOW,
        )
        is None
    )


def test_heure_unibet_utc_pas_paris():
    # 2611021945 = 2 nov 2026 19:45. C'est l'heure UTC de Lorient–Brest ce jour-là
    # chez PMU et Smarkets. En heure de Paris ce serait 18:45 UTC, qui ne colle pas.
    from grotonome.sources.parse import parse_unibet_kickoff

    assert parse_unibet_kickoff("2611021945") == datetime(2026, 11, 2, 19, 45, tzinfo=timezone.utc)


def test_alias_om_et_ol():
    assert same_team("OM", "Olympique de Marseille")
    assert same_team("OL", "Olympique Lyonnais")
    assert not same_team("OL", "Lens")
    assert not same_team("OM", "Monaco")


def test_unibet_suspendu_ecarte():
    payload = {
        "items": {
            "e1": {"a": "Lorient", "b": "Brest", "start": "2611021945"},
            "m1": {"parent": "e1", "style": "WIN_DRAW_WIN"},
            "o1": {"parent": "m1", "desc": "Lorient", "price": "2,30", "status": "SUSPENDED"},
            "o2": {"parent": "m1", "desc": "N", "price": "3,00", "status": "OPEN"},
            "o3": {"parent": "m1", "desc": "Brest", "price": "3,00", "status": "OPEN"},
        }
    }
    assert parse_unibet_page(payload, competition="ligue 1", captured_at=NOW) == []


def test_reglement_apres_minuit_utc():
    from grotonome.journal import record

    item = Proposal(
        competition="mls",
        home="Portland",
        away="Houston",
        kickoff=datetime(2026, 11, 3, 0, 30, tzinfo=timezone.utc),
        side=0,
        selection="Portland",
        bookmaker="winamax",
        odds=1.64,
        fair_p=0.55,
        ev=0.02,
        stake_fraction=0.01,
        overround=0.05,
        sharp_sources=("pinnacle",),
        devig="power",
    )
    journal = record([], [item], now=NOW)
    settle(journal, [{"home": "Portland", "away": "Houston", "date": "2026-11-02", "result": "H"}])
    assert journal[0]["result"] == "H"
    # Deux dates, deux résultats : on ne choisit pas.
    journal[0]["result"] = None
    journal[0]["pnl"] = None
    settle(
        journal,
        [
            {"home": "Portland", "away": "Houston", "date": "2026-11-02", "result": "H"},
            {"home": "Portland", "away": "Houston", "date": "2026-11-03", "result": "A"},
        ],
    )
    assert journal[0]["result"] is None


def test_winamax_prematch_seulement():
    html = """
    <script>
    PRELOADED_STATE = {"matches":{"1":{"sportId":1,"status":"PREMATCH","competitor1Name":"Lorient","competitor2Name":"Brest","mainBetId":10,"matchStart":1793634300,"tournamentId":4},"2":{"sportId":1,"status":"LIVE","competitor1Name":"A","competitor2Name":"B","mainBetId":11,"matchStart":1793634300}},
    "bets":{"10":{"available":true,"betTitle":"Résultat","outcomes":[1,2,3]},"11":{"available":true,"betTitle":"Résultat","outcomes":[4,5,6]}},
    "outcomes":{"1":{"label":"Lorient","code":"1","available":true},"2":{"label":"Match nul","code":"x","available":true},"3":{"label":"Brest","code":"2","available":true}},
    "odds":{"1":2.3,"2":3.1,"3":2.9},
    "tournaments":{"4":{"tournamentName":"Ligue 1"}}};
    </script>
    """
    found = parse_winamax_html(html, captured_at=NOW)
    assert len(found) == 1
    assert found[0].odds == (2.3, 3.1, 2.9)
    assert found[0].competition == "Ligue 1"
    assert found[0].kickoff == datetime.fromtimestamp(1793634300, tz=timezone.utc)


def test_clv_ne_choisit_pas_avec_la_cloture():
    # À l'ouverture le domicile est +EV. À la clôture l'extérieur le devient.
    # On mesure la CLV du domicile, pas celle de l'extérieur.
    rows = [
        {
            "at": "2026-11-02T12:00:00+00:00",
            "kind": "book",
            "source": "winamax",
            "home": "Lorient",
            "away": "Brest",
            "kickoff": "2026-11-02T19:45:00+00:00",
            "odds": [2.20, 3.40, 3.40],
        },
        {
            "at": "2026-11-02T12:00:00+00:00",
            "kind": "sharp",
            "source": "pinnacle",
            "home": "Lorient",
            "away": "Brest",
            "kickoff": "2026-11-02T19:45:00+00:00",
            "odds": [2.00, 3.50, 3.60],
        },
        {
            "at": "2026-11-02T18:00:00+00:00",
            "kind": "sharp",
            "source": "pinnacle",
            "home": "Lorient",
            "away": "Brest",
            "kickoff": "2026-11-02T19:45:00+00:00",
            "probs": [0.30, 0.20, 0.50],
        },
    ]
    measured = french_clv(rows)
    assert measured["n"] == 1
    # Côté domicile : 2,20 × 0,30 − 1 = −0,34. Pas 2,20 × autre chose choisi à la clôture.
    assert abs(measured["clv_mean"] - (2.20 * 0.30 - 1)) < 1e-9
