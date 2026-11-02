"""Parseurs sur extraits réels réduits, et pipeline avec sources factices."""

from datetime import datetime, timedelta, timezone

import pytest

from grotonome.http import redact
from grotonome.models import FetchReport, SharpPrice, SoftPrice
from grotonome.names import same_team
from grotonome.pipeline import analyze
from grotonome.sources.parse import (
    american_to_decimal,
    competition_key,
    parse_netbet_html,
    parse_pinnacle_matchups,
    parse_pinnacle_moneyline,
    parse_pmu_payload,
    parse_smarkets_quotes,
    parse_unibet_kickoff,
    parse_unibet_page,
)

NOW = datetime(2026, 11, 2, 1, 15, tzinfo=timezone.utc)


def test_noms():
    assert same_team("Paris SG", "Paris Saint-Germain")
    assert same_team("FC Lorient", "Lorient")
    assert not same_team("Lyon", "Lens")
    assert not same_team("OM", "OL")


def test_competitions():
    assert competition_key("Ligue 1 McDonalds") == "ligue 1"
    assert competition_key("Ligue 2 BKT") == "ligue 2"
    assert competition_key("LaLiga 2") is None
    assert competition_key("Serie A") == "serie a"
    assert competition_key("Women Premier League") is None


def test_heure_unibet():
    assert parse_unibet_kickoff("2611021945") == datetime(2026, 11, 2, 19, 45, tzinfo=timezone.utc)


def test_unibet_1n2():
    payload = {
        "items": {
            "e1": {"a": "Lorient", "b": "Brest", "start": "2611021945"},
            "m1": {"parent": "e1", "style": "WIN_DRAW_WIN", "desc": "1 N 2"},
            "o1": {"parent": "m1", "desc": "Lorient", "price": "2,30"},
            "o2": {"parent": "m1", "desc": "N", "price": "3,00"},
            "o3": {"parent": "m1", "desc": "Brest", "price": "3,00"},
        }
    }
    found = parse_unibet_page(payload, competition="ligue 1", captured_at=NOW)
    assert len(found) == 1
    assert found[0].odds == (2.30, 3.00, 3.00)


def test_pmu_divise_par_mille():
    payload = {
        "events": [
            {
                "event": {
                    "homeName": "Lorient",
                    "awayName": "Brest",
                    "start": "2026-11-02T19:45:00Z",
                },
                "betOffers": [
                    {
                        "criterion": {"englishLabel": "Full Time"},
                        "betOfferType": {"englishName": "Match"},
                        "outcomes": [
                            {"label": "1", "odds": 2280, "changedDate": "2026-10-30T08:20:18Z"},
                            {"label": "X", "odds": 3100, "changedDate": "2026-10-30T08:20:18Z"},
                            {"label": "2", "odds": 2880, "changedDate": "2026-10-30T08:20:18Z"},
                        ],
                    }
                ],
            }
        ]
    }
    found = parse_pmu_payload(payload, competition="ligue 1", captured_at=NOW)
    assert found[0].odds == (2.28, 3.10, 2.88)
    assert found[0].movement_at == datetime(2026, 10, 30, 8, 20, 18, tzinfo=timezone.utc)


def test_netbet_odds_display_pas_la_variable():
    html = (
        r'label:"Paris SG \u002F Troyes",url:"/e/1",start:"2026-11-07T20:45:00.000+01:00",'
        r'choices:{question:{label:"Qui va gagner le match ?"},choices:['
        r'{odd:1.11,actor:{label:"Paris SG",abbreviation:"Paris SG",short:b,flag:f,actorLabel:"Paris SG"},oddsDisplay:"1.11"},'
        r'{odd:H,actor:{label:"Nul",abbreviation:"Nul",short:b,flag:f,actorLabel:"Nul"},oddsDisplay:"8.00"},'
        r'{odd:13.5,actor:{label:"Troyes",abbreviation:"Troyes",short:b,flag:f,actorLabel:"Troyes"},oddsDisplay:"13.50"}'
        r"]}"
    )
    found = parse_netbet_html(html, competition="ligue 1", captured_at=NOW)
    assert len(found) == 1
    assert found[0].odds == (1.11, 8.0, 13.5)
    assert found[0].home == "Paris SG"


def test_smarkets_milieu():
    # Prix en dix-millièmes de probabilité. Achat 3900, vente 4100 → milieu 0,40.
    contracts = [
        {"id": "1", "contract_type": {"name": "HOME"}},
        {"id": "2", "contract_type": {"name": "DRAW"}},
        {"id": "3", "contract_type": {"name": "AWAY"}},
    ]
    quotes = {
        "1": {"bids": [{"price": 3900}], "offers": [{"price": 4100}]},
        "2": {"bids": [{"price": 2900}], "offers": [{"price": 3100}]},
        "3": {"bids": [{"price": 2900}], "offers": [{"price": 3100}]},
    }
    quote = parse_smarkets_quotes(
        event_name="Lorient vs Brest",
        kickoff=NOW,
        contracts=contracts,
        quotes=quotes,
        captured_at=NOW,
    )
    assert quote is not None
    assert quote.probs[0] == 0.40
    assert quote.probs[1] == 0.30


def test_smarkets_sans_un_cote_est_absent():
    contracts = [
        {"id": "1", "contract_type": {"name": "HOME"}},
        {"id": "2", "contract_type": {"name": "DRAW"}},
        {"id": "3", "contract_type": {"name": "AWAY"}},
    ]
    quotes = {
        "1": {"bids": [{"price": 3900}], "offers": []},
        "2": {"bids": [{"price": 2900}], "offers": [{"price": 3100}]},
        "3": {"bids": [{"price": 2900}], "offers": [{"price": 3100}]},
    }
    assert (
        parse_smarkets_quotes(
            event_name="Lorient vs Brest",
            kickoff=NOW,
            contracts=contracts,
            quotes=quotes,
            captured_at=NOW,
        )
        is None
    )


def test_americain():
    assert american_to_decimal(118) == pytest.approx(2.18)
    assert american_to_decimal(-110) == 100 / 110 + 1
    # −353 américain : 100/353 + 1.
    assert american_to_decimal(-353) == pytest.approx(100 / 353 + 1)


def test_pinnacle_noms_et_moneyline():
    payload = [
        {
            "id": 5,
            "type": "matchup",
            "parentId": None,
            "isLive": False,
            "startTime": "2026-11-02T19:45:00Z",
            "league": {"name": "France - Ligue 1"},
            "participants": [
                {"alignment": "home", "name": "Lorient"},
                {"alignment": "away", "name": "Brest"},
            ],
        },
        {"id": 6, "type": "matchup", "parentId": 5, "isLive": False, "participants": []},
    ]
    found = parse_pinnacle_matchups(payload, captured_at=NOW)
    assert len(found) == 1
    assert found[0].home == "Lorient" and found[0].external_id == "5"
    odds = parse_pinnacle_moneyline(
        [
            {
                "type": "moneyline",
                "period": 0,
                "isAlternate": False,
                "status": "open",
                "prices": [
                    {"designation": "home", "price": -353},
                    {"designation": "draw", "price": 391},
                    {"designation": "away", "price": 635},
                ],
            }
        ]
    )
    assert odds[0] == pytest.approx(100 / 353 + 1)
    assert odds[1] == pytest.approx(391 / 100 + 1)
    assert odds[2] == pytest.approx(635 / 100 + 1)


def test_pipeline_une_source_morte_ne_bloque_pas():
    kick = datetime(2026, 11, 2, 19, 45, tzinfo=timezone.utc)
    soft = SoftPrice("unibet", "ligue 1", "Lorient", "Brest", kick, (2.30, 3.00, 4.20), NOW)
    # Probabilités déjà presque justes. Extérieur 0,28 × 4,20 − 1 = 0,176.
    sharp = SharpPrice(
        "smarkets", "", "Lorient", "Brest", kick, NOW, probs=(0.42, 0.30, 0.28)
    )
    dead = FetchReport("pmu", "book", False, "HTTP 410", 0.1)
    alive = FetchReport("unibet", "book", True, "ligue 1: 1", 0.2, 1, [soft])
    ref = FetchReport("smarkets", "sharp", True, "1", 0.2, 1, sharp=[sharp])
    result = analyze([dead, alive, ref])
    assert any(not report.ok for report in result.reports)
    assert len(result.proposals) == 1
    assert result.proposals[0].selection == "Brest"
    assert result.proposals[0].ev > 0
    assert result.proposals[0].bookmaker == "unibet"


def test_desaccord_sharp_ecarte_le_pari():
    kick = datetime(2026, 11, 2, 19, 45, tzinfo=timezone.utc)
    soft = SoftPrice("netbet", "ligue 1", "Lorient", "Brest", kick, (3.00, 3.20, 2.40), NOW)
    a = SharpPrice("smarkets", "", "Lorient", "Brest", kick, NOW, probs=(0.55, 0.25, 0.20))
    b = SharpPrice("matchbook", "", "Lorient", "Brest", kick, NOW, probs=(0.30, 0.30, 0.40))
    reports = [
        FetchReport("netbet", "book", True, "1", 0.1, 1, [soft]),
        FetchReport("smarkets", "sharp", True, "1", 0.1, 1, sharp=[a]),
        FetchReport("matchbook", "sharp", True, "1", 0.1, 1, sharp=[b]),
    ]
    result = analyze(reports)
    assert result.proposals == []
    assert result.skipped and "désaccord" in result.skipped[0]["reason"]


def test_sans_sharp_pas_de_pari():
    kick = datetime(2026, 11, 2, 19, 45, tzinfo=timezone.utc)
    soft = SoftPrice("unibet", "ligue 1", "Lorient", "Brest", kick, (4.0, 4.0, 4.0), NOW)
    result = analyze([FetchReport("unibet", "book", True, "1", 0.1, 1, [soft])])
    assert result.proposals == []
    assert result.unmatched == 1


def test_redaction_secret():
    assert "super-secret" not in redact("https://example.test/odds?apiKey=super-secret&x=1")
    assert "apiKey=***" in redact("https://example.test/odds?apiKey=super-secret&x=1")


def test_pricer_appele_seulement_si_apparie():
    kick = datetime(2026, 11, 2, 19, 45, tzinfo=timezone.utc)
    soft = SoftPrice("unibet", "ligue 1", "Lorient", "Brest", kick, (2.2, 3.4, 4.5), NOW)
    stub = SharpPrice(
        "smarkets", "", "Lorient", "Brest", kick, NOW, external_id="99"
    )
    other = SharpPrice(
        "smarkets",
        "",
        "Ailleurs",
        "Ville",
        kick + timedelta(days=1),
        NOW,
        external_id="100",
    )
    calls = []

    def pricer(item):
        calls.append(item.external_id)
        return SharpPrice(
            "smarkets", "", item.home, item.away, item.kickoff, NOW, probs=(0.40, 0.30, 0.30)
        )

    reports = [
        FetchReport("unibet", "book", True, "1", 0.1, 1, [soft]),
        FetchReport("smarkets", "sharp", True, "2", 0.1, 2, sharp=[stub, other]),
    ]
    result = analyze(reports, pricer=pricer)
    assert calls == ["99"]
    assert result.proposals


def test_shopping_deux_books():
    kick = datetime(2026, 11, 2, 19, 45, tzinfo=timezone.utc)
    a = SoftPrice("unibet", "ligue 1", "Lorient", "Brest", kick, (2.2, 3.4, 3.2), NOW)
    b = SoftPrice("netbet", "ligue 1", "Lorient", "Brest", kick, (2.0, 3.6, 4.2), NOW)
    reports = [
        FetchReport("unibet", "book", True, "1", 0.1, 1, [a]),
        FetchReport("netbet", "book", True, "1", 0.1, 1, [b]),
    ]
    result = analyze(reports)
    assert result.shopping[0]["surebet"] is True
    assert result.proposals == []
