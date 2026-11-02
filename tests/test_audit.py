"""Chaque test échouait sur le code d'avant l'audit : faux pari, chiffre trompeur ou panne invisible."""

import importlib.util
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from grotonome.http import HttpError, redact
from grotonome.journal import performance
from grotonome.metrics import mean_interval
from grotonome.models import FetchReport, SharpPrice, SoftPrice
from grotonome.names import normalize, same_team
from grotonome.pipeline import analyze
from grotonome.render import payload, telegram_text
from grotonome.results import fetch_results
from grotonome.sources.fetch import fetch_smarkets, probe_blocked
from grotonome.sources.parse import (
    competition_key,
    parse_matchbook_events,
    parse_netbet_html,
    parse_pmu_payload,
)

NOW = datetime(2026, 11, 2, 1, 15, tzinfo=timezone.utc)
KICK = datetime(2026, 11, 2, 19, 45, tzinfo=timezone.utc)


def _hist():
    spec = importlib.util.spec_from_file_location(
        "recherche_historique",
        Path(__file__).resolve().parents[1] / "scripts" / "recherche_historique.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_alias_avant_retrait_des_mots():
    # « fc » était retiré avant l'alias : Paris FC devenait Paris, Barcelona SC devenait Barcelona.
    assert normalize("Paris FC") == "paris fc"
    assert not same_team("Paris FC", "Paris")
    assert not same_team("Paris FC", "Paris Saint-Germain")
    assert not same_team("FC Barcelona", "Barcelona SC")
    assert same_team("Stade de Reims", "Reims")
    assert same_team("Olympique de Marseille", "Marseille")
    assert same_team("FC Lorient", "Lorient")
    assert not same_team("PFC Ludogorets Razgrad II", "PFC Ludogorets Razgrad")


def test_paris_fc_ne_prend_pas_la_cote_de_paris():
    soft = SoftPrice("netbet", "ligue 1", "Paris FC", "Troyes", KICK, (4.0, 3.4, 1.9), NOW)
    # Si « Paris FC » se confond avec « Paris », 0,40 × 4,0 − 1 = +60 % est un faux pari.
    sharp = SharpPrice(
        "pinnacle", "", "Paris", "Troyes", KICK, NOW, probs=(0.40, 0.30, 0.30)
    )
    result = analyze(
        [
            FetchReport("netbet", "book", True, "1", 0.1, 1, [soft]),
            FetchReport("pinnacle", "sharp", True, "1", 0.1, 1, sharp=[sharp]),
        ]
    )
    assert result.proposals == []


def test_championnat_n_est_pas_la_ligue_des_champions():
    assert competition_key("Championship") is None
    assert competition_key("Championnat de France") is None
    assert competition_key("Frauen-Bundesliga") is None
    assert competition_key("Dames Ligue 1") is None
    assert competition_key("Ligue des Champions") == "champions league"
    assert competition_key("Ligue 1 McDonalds") == "ligue 1"


def test_ligues_differentes_ne_s_apparient_pas():
    soft = SoftPrice("unibet", "ligue 1", "Arsenal", "Chelsea", KICK, (3.2, 3.4, 2.4), NOW)
    wrong = SharpPrice(
        "pinnacle",
        "England - Premier League",
        "Arsenal",
        "Chelsea",
        KICK,
        NOW,
        probs=(0.45, 0.28, 0.27),
    )
    right = SharpPrice(
        "pinnacle",
        "France - Ligue 1",
        "Arsenal",
        "Chelsea",
        KICK,
        NOW,
        probs=(0.45, 0.28, 0.27),
    )
    blocked = analyze(
        [
            FetchReport("unibet", "book", True, "1", 0.1, 1, [soft]),
            FetchReport("pinnacle", "sharp", True, "1", 0.1, 1, sharp=[wrong]),
        ]
    )
    assert blocked.proposals == []
    kept = analyze(
        [
            FetchReport("unibet", "book", True, "1", 0.1, 1, [soft]),
            FetchReport("pinnacle", "sharp", True, "1", 0.1, 1, sharp=[right]),
        ]
    )
    assert kept.proposals


def test_match_commence_n_est_pas_propose():
    past = NOW - timedelta(hours=1)
    soft = SoftPrice("unibet", "ligue 1", "Lorient", "Brest", past, (4.0, 3.4, 2.2), NOW)
    sharp = SharpPrice("smarkets", "", "Lorient", "Brest", past, NOW, probs=(0.40, 0.30, 0.30))
    result = analyze(
        [
            FetchReport("unibet", "book", True, "1", 0.1, 1, [soft]),
            FetchReport("smarkets", "sharp", True, "1", 0.1, 1, sharp=[sharp]),
        ]
    )
    assert result.proposals == []
    assert result.skipped and "coup d'envoi" in result.skipped[0]["reason"]


def test_pinnacle_compte_une_seule_fois():
    # Deux fois Pinnacle à 0,50 et Smarkets à 0,42 : la moyenne à trois voix (0,473)
    # rend la cote 2,15 positive. Une voix par source (0,46) la laisse négative.
    soft = SoftPrice("unibet", "ligue 1", "Lorient", "Brest", KICK, (2.15, 3.4, 3.6), NOW)
    first = SharpPrice("pinnacle", "", "Lorient", "Brest", KICK, NOW, probs=(0.50, 0.25, 0.25))
    second = SharpPrice("pinnacle", "ligue 1", "Lorient", "Brest", KICK, NOW, probs=(0.50, 0.25, 0.25))
    market = SharpPrice("smarkets", "", "Lorient", "Brest", KICK, NOW, probs=(0.42, 0.29, 0.29))
    result = analyze(
        [
            FetchReport("unibet", "book", True, "1", 0.1, 1, [soft]),
            FetchReport("pinnacle", "sharp", True, "1", 0.1, 1, sharp=[first]),
            FetchReport("the-odds-api", "sharp", True, "1", 0.1, 1, sharp=[second]),
            FetchReport("smarkets", "sharp", True, "1", 0.1, 1, sharp=[market]),
        ]
    )
    assert result.proposals == []


def test_probabilites_incoherentes_ne_créent_pas_de_pari():
    soft = SoftPrice("unibet", "ligue 1", "Lorient", "Brest", KICK, (5.0, 5.0, 5.0), NOW)
    garbage = SharpPrice("smarkets", "", "Lorient", "Brest", KICK, NOW, probs=(0.9, 0.9, 0.9))
    zero = SharpPrice("matchbook", "", "Lorient", "Brest", KICK, NOW, probs=(0.0, 0.5, 0.5))
    result = analyze(
        [
            FetchReport("unibet", "book", True, "1", 0.1, 1, [soft]),
            FetchReport("smarkets", "sharp", True, "1", 0.1, 1, sharp=[garbage]),
            FetchReport("matchbook", "sharp", True, "1", 0.1, 1, sharp=[zero]),
        ]
    )
    assert result.proposals == []


def test_plafond_tarif_le_match_le_plus_proche():
    soon = KICK
    later = KICK + timedelta(days=2)
    soft_soon = SoftPrice("unibet", "ligue 1", "Lorient", "Brest", soon, (2.2, 3.4, 4.5), NOW)
    soft_later = SoftPrice("unibet", "ligue 1", "Nice", "Lille", later, (2.2, 3.4, 4.5), NOW)
    late_stub = SharpPrice("smarkets", "", "Nice", "Lille", later, NOW, external_id="late")
    soon_stub = SharpPrice("smarkets", "", "Lorient", "Brest", soon, NOW, external_id="soon")
    calls = []

    def pricer(item):
        calls.append(item.external_id)
        return SharpPrice(
            "smarkets", "", item.home, item.away, item.kickoff, NOW, probs=(0.40, 0.30, 0.30)
        )

    result = analyze(
        [
            FetchReport("unibet", "book", True, "2", 0.1, 2, [soft_soon, soft_later]),
            FetchReport("smarkets", "sharp", True, "2", 0.1, 2, sharp=[late_stub, soon_stub]),
        ],
        pricer=pricer,
        price_limit=1,
    )
    assert calls == ["soon"]
    assert result.unpriced == 1
    text = telegram_text(result, now=NOW, bankroll=None)
    assert "non tarifés" in text


def test_shopping_ne_fusionne_pas_deux_barcelone():
    a = SoftPrice("unibet", "ligue 1", "FC Barcelona", "Emelec", KICK, (2.2, 3.4, 3.2), NOW)
    b = SoftPrice("pmu", "ligue 1", "Barcelona SC", "Emelec", KICK, (2.0, 3.6, 4.2), NOW)
    result = analyze(
        [
            FetchReport("unibet", "book", True, "1", 0.1, 1, [a]),
            FetchReport("pmu", "book", True, "1", 0.1, 1, [b]),
        ]
    )
    assert result.shopping == []


def test_pmu_dernier_mouvement_et_lignes_incoherentes():
    payload = {
        "events": [
            {
                "event": {"homeName": "Lorient", "awayName": "Brest", "start": "2026-11-02T19:45:00Z", "state": "STARTED"},
                "betOffers": [
                    {
                        "criterion": {"englishLabel": "Full Time"},
                        "betOfferType": {"englishName": "Match"},
                        "outcomes": [
                            {"label": "1", "odds": 5000, "status": "OPEN", "participant": "Lorient"},
                            {"label": "X", "odds": 3000, "status": "OPEN"},
                            {"label": "2", "odds": 1800, "status": "OPEN", "participant": "Brest"},
                        ],
                    }
                ],
            },
            {
                "event": {"homeName": "Lorient", "awayName": "Brest", "start": "2026-11-02T19:45:00Z"},
                "betOffers": [
                    {
                        "criterion": {"englishLabel": "Full Time"},
                        "betOfferType": {"englishName": "Match"},
                        "outcomes": [
                            {"label": "1", "odds": 2280, "status": "OPEN", "changedDate": "2026-10-30T08:20:18Z", "participant": "Brest"},
                            {"label": "X", "odds": 3100, "status": "OPEN", "changedDate": "2026-11-02T01:00:00Z"},
                            {"label": "2", "odds": 2880, "status": "SUSPENDED", "changedDate": "2026-11-02T01:00:00Z", "participant": "Brest"},
                        ],
                    }
                ],
            },
            {"event": {"homeName": "Nice", "awayName": "Lille", "start": "2026-11-08T19:45:00Z"}, "betOffers": [{"outcomes": [{}]}]},
            {
                "event": {"homeName": "Lens", "awayName": "Marseille", "start": "2026-11-08T19:45:00Z", "state": "NOT_STARTED"},
                "betOffers": [
                    {
                        "criterion": {"englishLabel": "Full Time"},
                        "betOfferType": {"englishName": "Match"},
                        "outcomes": [
                            {"label": "1", "odds": 1900, "status": "OPEN", "participant": "Lens", "changedDate": "2026-10-01T00:00:00Z"},
                            {"label": "X", "odds": 3400, "status": "OPEN", "changedDate": "2026-11-02T00:30:00Z"},
                            {"label": "2", "odds": 2800, "status": "OPEN", "participant": "Marseille", "changedDate": "2026-11-02T00:30:00Z"},
                        ],
                    }
                ],
            },
        ]
    }
    found = parse_pmu_payload(payload, competition="ligue 1", captured_at=NOW)
    assert len(found) == 1
    assert found[0].home == "Lens"
    assert found[0].movement_at == datetime(2026, 11, 2, 0, 30, tzinfo=timezone.utc)


def test_netbet_ignore_la_mi_temps():
    html = (
        'label:"Lorient / Brest",url:"/e/1",start:"2026-11-02T20:45:00+01:00",'
        'choices:{question:{label:"Qui va gagner la 1ère mi-temps ?"},choices:['
        '{actor:{actorLabel:"Lorient"},oddsDisplay:"3.40"},'
        '{actor:{actorLabel:"Nul"},oddsDisplay:"2.10"},'
        '{actor:{actorLabel:"Brest"},oddsDisplay:"3.20"}'
        "]}"
        'choices:{question:{label:"Qui va gagner le match ?"},choices:['
        '{actor:{actorLabel:"Lorient"},oddsDisplay:"2.37"},'
        '{actor:{actorLabel:"Nul"},oddsDisplay:"3.05"},'
        '{actor:{actorLabel:"Brest"},oddsDisplay:"2.85"}'
        "]}"
    )
    found = parse_netbet_html(html, competition="ligue 1", captured_at=NOW)
    assert found[0].odds == (2.37, 3.05, 2.85)


def test_matchbook_ignore_le_live():
    def event(flag, start):
        return {
            "name": "Lorient vs Brest",
            "start": start,
            "in-running-flag": flag,
            "markets": [
                {
                    "name": "Match Odds",
                    "live": flag,
                    "runners": [
                        {
                            "name": "Lorient",
                            "prices": [
                                {"side": "win", "decimal-odds": 2.5, "available-amount": 40},
                                {"side": "lose", "decimal-odds": 1.7, "available-amount": 40},
                            ],
                        },
                        {
                            "name": "Draw",
                            "prices": [
                                {"side": "win", "decimal-odds": 3.4, "available-amount": 40},
                                {"side": "lose", "decimal-odds": 1.45, "available-amount": 40},
                            ],
                        },
                        {
                            "name": "Brest",
                            "prices": [
                                {"side": "win", "decimal-odds": 3.1, "available-amount": 40},
                                {"side": "lose", "decimal-odds": 1.5, "available-amount": 40},
                            ],
                        },
                    ],
                }
            ],
        }

    live = parse_matchbook_events(
        {"events": [event(True, "2026-11-02T00:25:00Z")]}, captured_at=NOW
    )
    assert live == []
    fresh = parse_matchbook_events(
        {"events": [event(False, "2026-11-02T19:45:00Z")]}, captured_at=NOW
    )
    assert len(fresh) == 1


def test_intervalle_nul_et_paris_du_meme_match():
    flat = mean_interval([-1.0, -1.0, -1.0])
    assert flat.mean == -1
    assert flat.low is None
    same = performance(
        [
            {"home": "Lorient", "away": "Brest", "kickoff": KICK.isoformat(), "pnl": 1.0, "odds": 2.0},
            {"home": "Lorient", "away": "Brest", "kickoff": KICK.isoformat(), "pnl": -1.0, "odds": 2.0},
        ]
    )
    assert same["n_settled"] == 2
    assert same["roi_low"] is None
    assert "match" in (same["roi_note"] or "")
    split = performance(
        [
            {"home": "Lorient", "away": "Brest", "kickoff": KICK.isoformat(), "pnl": 1.0, "odds": 2.0},
            {"home": "Nice", "away": "Lille", "kickoff": KICK.isoformat(), "pnl": -1.0, "odds": 2.0},
        ]
    )
    assert split["roi_low"] == pytest.approx(mean_interval([1.0, -1.0]).low)


def test_corps_http_et_jeton_telegram_sont_masques():
    err = HttpError(401, "https://api.example.test/v4?apiKey=SECRET", "invalid apiKey=SECRET")
    assert "SECRET" not in str(err)
    assert "123456:ABCDE" not in redact("https://api.telegram.org/bot123456:ABCDE/sendMessage")


def test_html_de_resultats_n_est_pas_un_succes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "grotonome.results.get_text",
        lambda url, timeout=30: "<html><title>blocked</title></html>",
    )
    found, note = fetch_results(tmp_path, day=date(2026, 11, 2))
    assert found == []
    assert "non CSV" in note
    assert "ok" not in note
    assert list(tmp_path.glob("*.csv")) == []


def test_sonde_en_timeout_n_arrete_pas_le_releve(monkeypatch):
    def boom(url, timeout=12):
        raise TimeoutError("timed out")

    monkeypatch.setattr("grotonome.sources.fetch.get_text", boom)
    reports = probe_blocked(sleep=0)
    assert reports
    assert all(not report.ok for report in reports)


def test_smarkets_garde_la_premiere_page_si_la_suivante_tombe(monkeypatch):
    def fake(url, timeout=20):
        if "pagination_last_id" in url:
            raise HttpError(429, url, "")
        return {
            "events": [
                {"id": "8", "name": "Sans heure"},
                {"id": "9", "name": "Lorient vs Brest", "start_datetime": "2026-11-02T19:45:00Z"},
            ],
            "pagination": {"next_page": "?pagination_last_id=9"},
        }

    monkeypatch.setattr("grotonome.sources.fetch.get_json", fake)
    report = fetch_smarkets(captured_at=NOW, sleep=0)
    assert report.ok
    assert report.n == 1
    assert "429" in report.detail


def test_telegram_montre_la_panne_partielle_et_les_ecarts():
    reports = [
        FetchReport("pmu", "book", True, "ligue 1: 10, serie a: HTTP 410", 1.2, 10),
    ]
    result = analyze(reports)
    result.skipped.append({"match": "A – B", "bookmaker": "pmu", "reason": "références en désaccord"})
    text = telegram_text(result, now=NOW, bankroll=None)
    assert "HTTP 410" in text
    assert "Écartés : 1" in text
    body = payload(result, now=NOW, performance={"n_bets": 0}, bankroll=None)
    assert "unpriced" in body


def test_page_ne_ment_pas_sur_pinnacle_ni_sur_le_shopping_vide():
    html = Path("site/index.html").read_text(encoding="utf-8")
    assert "ou pas de surebet" not in html
    assert "Pinnacle lues sans clé" in html
    assert "Matchbook" in html
    assert "function esc" in html or "const esc" in html


def test_backtest_sans_cloture_et_sans_ev_nulle():
    hist = _hist()
    day = datetime(2024, 8, 15)
    base = {
        "date": day,
        "div": "E0",
        "result": "H",
        "opening": (2.0, 3.6, 4.2),
        "soft": (3.0, 3.4, 3.2),
        "closing": None,
        "goals": (1, 0),
    }
    bets = hist.run([base], 0.0)
    assert len(bets) == 1
    assert bets[0]["clv"] is None
    zero = dict(base, opening=(2.0, 4.0, 4.0), soft=(2.0, 4.0, 4.0))
    assert hist.run([zero], 0.0) == []


def test_frequences_sans_fuite_du_jour_et_sans_plantage():
    hist = _hist()
    rows = []
    for index, result in enumerate(["H"] * 68 + ["D"] * 9 + ["A"] * 3):
        rows.append(
            {
                "date": datetime(2024, 1, 1) + timedelta(days=index),
                "div": "E0",
                "result": result,
                "opening": (1.15, 7, 25),
                "soft": (1.15, 7, 25),
                "closing": (1.15, 7, 25),
                "goals": (1, 0),
            }
        )
    for _ in range(8):
        rows.append(
            {
                "date": datetime(2024, 8, 15),
                "div": "E0",
                "result": "A",
                "opening": (1.15, 7, 25),
                "soft": (1.15, 7, 25),
                "closing": (1.15, 7, 25),
                "goals": (0, 1),
            }
        )
    assert hist.frequency_model(rows) == []
    certain = []
    for index in range(80):
        certain.append(
            {
                "date": datetime(2024, 1, 1) + timedelta(days=index),
                "div": "E0",
                "result": "H",
                "opening": (1.5, 4, 6),
                "soft": (1.5, 4, 6),
                "closing": (1.5, 4, 6),
                "goals": (1, 0),
            }
        )
    certain.append(
        {
            "date": datetime(2024, 8, 15),
            "div": "E0",
            "result": "H",
            "opening": (1.5, 4, 6),
            "soft": (1.5, 4, 6),
            "closing": (1.5, 4, 6),
            "goals": (1, 0),
        }
    )
    assert isinstance(hist.frequency_model(certain), list)
