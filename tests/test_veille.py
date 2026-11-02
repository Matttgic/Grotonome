"""Anti-doublon des alertes et recul après 403 ou 429."""

from datetime import datetime, timedelta, timezone

from grotonome.alertes import odds_rose, remember_alerts, select_alerts
from grotonome.cli import pause_seconds
from grotonome.models import Proposal
from grotonome.recul import backoff_delay, blocked_until, observe

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)


def _bet(odds: float) -> Proposal:
    return Proposal(
        competition="ligue 1",
        home="Lorient",
        away="Brest",
        kickoff=datetime(2026, 11, 2, 19, 45, tzinfo=timezone.utc),
        side=0,
        selection="Lorient",
        bookmaker="winamax",
        odds=odds,
        fair_p=0.5,
        ev=0.05,
        stake_fraction=0.01,
        overround=0.08,
        sharp_sources=("pinnacle",),
        devig="power",
    )


def test_premiere_alerte_puis_silence_puis_hausse():
    memory: dict = {}
    first = select_alerts([_bet(2.10)], memory)
    assert len(first) == 1
    remember_alerts(memory, first)
    assert select_alerts([_bet(2.10)], memory) == []
    assert select_alerts([_bet(2.12)], memory) == []
    again = select_alerts([_bet(2.20)], memory)
    assert len(again) == 1
    assert odds_rose(2.10, 2.20)
    assert not odds_rose(2.20, 2.10)


def test_recul_403_puis_429_puis_succes():
    state: dict = {}
    observe(state, "unibet", ok=False, detail="HTTP 403", now=NOW)
    assert blocked_until(state, "unibet", NOW + timedelta(minutes=10)) is not None
    assert backoff_delay(1) == timedelta(minutes=15)
    observe(state, "unibet", ok=False, detail="HTTP 429", now=NOW + timedelta(minutes=16))
    assert state["unibet"]["fails"] == 2
    assert backoff_delay(2) == timedelta(minutes=30)
    assert backoff_delay(4) == timedelta(minutes=120)
    observe(state, "unibet", ok=True, detail="ligue 1: 10", now=NOW + timedelta(hours=2))
    assert "unibet" not in state
    assert blocked_until(state, "unibet", NOW) is None


def test_une_erreur_autre_que_403_ne_fait_pas_reculer():
    state: dict = {}
    observe(state, "pmu", ok=False, detail="HTTP 500", now=NOW)
    assert state == {}


def test_pause_entre_deux_releves():
    assert pause_seconds(90, 360) == 270
    assert pause_seconds(400, 360) == 0
