"""Suivi : première cote conservée, clôture postérieure, résultat manquant laissé vide."""

from datetime import datetime, timedelta, timezone

from grotonome.journal import attach_closes, performance, proposal_id, record, settle
from grotonome.models import Proposal
from grotonome.results import parse_results_csv, season_code

NOW = datetime(2026, 11, 2, 11, 0, tzinfo=timezone.utc)
KICK = datetime(2026, 11, 2, 19, 45, tzinfo=timezone.utc)


def _proposal(odds=2.40):
    return Proposal(
        competition="ligue 1",
        home="Lorient",
        away="Brest",
        kickoff=KICK,
        side=0,
        selection="Lorient",
        bookmaker="netbet",
        odds=odds,
        fair_p=0.45,
        ev=0.08,
        stake_fraction=0.01,
        overround=0.07,
        sharp_sources=("smarkets",),
        devig="power",
    )


def test_premiere_cote_conservee():
    journal = record([], [_proposal(2.40)], now=NOW)
    record(journal, [_proposal(2.80)], now=NOW + timedelta(hours=2))
    assert len(journal) == 1
    assert journal[0]["odds"] == 2.40
    assert proposal_id(_proposal()) == journal[0]["id"]


def test_cloture_apres_la_proposition_seulement():
    journal = record([], [_proposal()], now=NOW)
    earlier = {
        "home": "Lorient",
        "away": "Brest",
        "kickoff": KICK.isoformat(),
        "observed_at": (NOW - timedelta(hours=1)).isoformat(),
        "fair_p": [0.9, 0.05, 0.05],
    }
    later = {
        "home": "Lorient",
        "away": "Brest",
        "kickoff": KICK.isoformat(),
        "observed_at": (NOW + timedelta(hours=4)).isoformat(),
        "fair_p": [0.42, 0.30, 0.28],
    }
    after_kick = {
        "home": "Lorient",
        "away": "Brest",
        "kickoff": KICK.isoformat(),
        "observed_at": (KICK + timedelta(minutes=10)).isoformat(),
        "fair_p": [0.10, 0.10, 0.80],
    }
    attach_closes(journal, [earlier, later, after_kick])
    assert journal[0]["closing_fair_p"] == 0.42
    # CLV = 2,40 × 0,42 − 1 = 0,008.
    stats = performance(journal)
    assert stats["clv_mean"] == 2.40 * 0.42 - 1
    assert stats["n_settled"] == 0
    assert stats["roi"] is None


def test_resultat_manquant_reste_manquant():
    journal = record([], [_proposal()], now=NOW)
    settle(journal, [])
    assert journal[0]["result"] is None
    assert journal[0]["pnl"] is None


def test_reglement_csv():
    text = "Div,Date,HomeTeam,AwayTeam,FTR\nF1,02/11/2026,Lorient,Brest,H\n"
    results = parse_results_csv(text)
    journal = record([], [_proposal(2.50)], now=NOW)
    settle(journal, results)
    assert journal[0]["result"] == "H"
    assert journal[0]["pnl"] == 1.50
    stats = performance(journal)
    assert stats["n_settled"] == 1
    assert stats["roi_low"] is None  # un seul pari : intervalle non calculé


def test_saison():
    assert season_code(datetime(2026, 11, 2).date()) == "2627"
    assert season_code(datetime(2026, 1, 15).date()) == "2526"
