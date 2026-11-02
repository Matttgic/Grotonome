"""Avertissement Betclic, cote figée, et mesure du retard SportyTrader."""

from datetime import datetime, timedelta, timezone

from grotonome.fraicheur import (
    RELAY_WARNING,
    SHARP_MOVE,
    betclic_key,
    measure_lag,
    remember_betclic_fair,
)
from grotonome.history import changed_rows
from grotonome.models import FetchReport, SharpPrice, SoftPrice
from grotonome.pipeline import analyze
from grotonome.render import alert_text, telegram_text

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
KICK = datetime(2026, 11, 2, 19, 45, tzinfo=timezone.utc)
ODDS = (2.30, 3.00, 4.20)


def _betclic(odds=ODDS):
    return SoftPrice("betclic", "ligue 1", "Lorient", "Brest", KICK, odds, NOW)


def _sharp(probs):
    return SharpPrice("smarkets", "", "Lorient", "Brest", KICK, NOW, probs=probs)


def _run(soft, probs, prior=None):
    reports = [
        FetchReport("betclic", "book", True, "1", 0.1, 1, [soft]),
        FetchReport("smarkets", "sharp", True, "1", 0.1, 1, sharp=[_sharp(probs)]),
    ]
    return analyze(reports, prior=prior)


def _prior(odds, fair):
    key = betclic_key("Lorient", "Brest", KICK.isoformat())
    return {key: {"odds": list(odds), "fair": list(fair), "at": "2026-11-02T11:00:00+00:00"}}


def test_avertissement_dans_la_liste_et_l_alerte():
    result = _run(_betclic(), (0.42, 0.30, 0.28))
    assert len(result.proposals) == 1
    bet = result.proposals[0]
    assert bet.bookmaker == "betclic"
    assert RELAY_WARNING in bet.warnings
    assert RELAY_WARNING in alert_text(bet, bankroll=100)
    page = telegram_text(result, now=NOW, bankroll=100)
    assert RELAY_WARNING in page


def test_un_autre_book_n_a_pas_l_avertissement():
    soft = SoftPrice("unibet", "ligue 1", "Lorient", "Brest", KICK, ODDS, NOW)
    reports = [
        FetchReport("unibet", "book", True, "1", 0.1, 1, [soft]),
        FetchReport("smarkets", "sharp", True, "1", 0.1, 1, sharp=[_sharp((0.42, 0.30, 0.28))]),
    ]
    result = analyze(reports, prior=_prior(ODDS, (0.50, 0.30, 0.20)))
    assert len(result.proposals) == 1
    assert result.proposals[0].warnings == ()


def test_cote_figee_ecartee_si_le_sharp_bouge_de_deux_points():
    # Juste actuelle : 0,42 / 0,30 / 0,28. Ancre 0,50 / 0,30 / 0,20. Écart domicile 0,08.
    assert SHARP_MOVE == 0.02
    result = _run(_betclic(), (0.42, 0.30, 0.28), _prior(ODDS, (0.50, 0.30, 0.20)))
    assert result.proposals == []
    assert result.skipped
    assert "figée" in result.skipped[0]["reason"]


def test_un_petit_mouvement_sharp_garde_la_cote_avec_l_avertissement():
    # Écart 0,01, sous le seuil de 0,02.
    result = _run(_betclic(), (0.42, 0.30, 0.28), _prior(ODDS, (0.41, 0.31, 0.28)))
    assert len(result.proposals) == 1
    assert RELAY_WARNING in result.proposals[0].warnings


def test_une_cote_betclic_qui_bouge_reste_proposee():
    # Seule l'issue extérieure change (4,20 → 4,50). 0,28 × 4,50 − 1 = 0,26.
    result = _run(
        _betclic((2.30, 3.00, 4.50)),
        (0.42, 0.30, 0.28),
        _prior(ODDS, (0.50, 0.30, 0.20)),
    )
    assert len(result.proposals) == 1
    assert result.proposals[0].odds == 4.50
    assert RELAY_WARNING in result.proposals[0].warnings


def test_l_ancre_ne_bouge_pas_tant_que_la_cote_betclic_est_la_meme():
    row = {
        "at": "2026-11-02T12:00:00+00:00",
        "kind": "book",
        "source": "betclic",
        "home": "Lorient",
        "away": "Brest",
        "kickoff": KICK.isoformat(),
        "odds": [2.30, 3.00, 4.20],
        "probs": None,
    }
    deltas, etat = changed_rows({}, [row])
    anchor = {"home": "Lorient", "away": "Brest", "kickoff": KICK.isoformat(), "fair": [0.50, 0.30, 0.20]}
    remember_betclic_fair(etat, [anchor], deltas)
    key = betclic_key("Lorient", "Brest", KICK.isoformat())
    assert etat[key]["fair"] == [0.50, 0.30, 0.20]
    same, etat = changed_rows(etat, [row])
    assert same == []
    remember_betclic_fair(
        etat,
        [{"home": "Lorient", "away": "Brest", "kickoff": KICK.isoformat(), "fair": [0.42, 0.30, 0.28]}],
        same,
    )
    assert etat[key]["fair"] == [0.50, 0.30, 0.20]
    moved = dict(row, odds=[2.10, 3.20, 4.40], at="2026-11-02T12:06:00+00:00")
    deltas, etat = changed_rows(etat, [moved])
    assert len(deltas) == 1
    remember_betclic_fair(
        etat,
        [{"home": "Lorient", "away": "Brest", "kickoff": KICK.isoformat(), "fair": [0.42, 0.30, 0.28]}],
        deltas,
    )
    assert etat[key]["fair"] == [0.42, 0.30, 0.28]


def _row(at, kind, source, odds=None, probs=None, minute=0):
    kick = KICK + timedelta(minutes=minute)
    return {
        "at": at,
        "kind": kind,
        "source": source,
        "home": "Lorient",
        "away": "Brest",
        "kickoff": kick.isoformat(),
        "odds": odds,
        "probs": probs,
    }


def test_retard_suivi_douze_minutes():
    rows = [
        _row("2026-11-02T12:00:00+00:00", "sharp", "pinnacle", odds=[2.10, 3.40, 3.60]),
        _row("2026-11-02T12:06:00+00:00", "sharp", "pinnacle", odds=[1.90, 3.50, 4.20]),
        _row("2026-11-02T12:00:00+00:00", "book", "betclic", odds=[2.40, 3.20, 3.10]),
        _row("2026-11-02T12:18:00+00:00", "book", "betclic", odds=[2.20, 3.40, 3.40]),
        _row("2026-11-02T12:00:00+00:00", "book", "unibet", odds=[2.30, 3.20, 3.20]),
        _row("2026-11-02T12:06:00+00:00", "book", "unibet", odds=[2.10, 3.40, 3.60]),
    ]
    report = measure_lag(rows)
    assert report["sharp"]["n_moves"] == 1
    assert report["sharp"]["n_followed"] == 1
    assert report["sharp"]["median_s"] == 720
    assert report["books"]["n_moves"] == 1
    assert report["books"]["median_s"] == 720
    assert report["too_small"] is True


def test_mouvement_sharp_sans_suivi_betclic_est_censure():
    rows = [
        _row("2026-11-02T12:00:00+00:00", "sharp", "smarkets", probs=[0.40, 0.30, 0.30]),
        _row("2026-11-02T12:06:00+00:00", "sharp", "smarkets", probs=[0.46, 0.27, 0.27]),
        _row("2026-11-02T12:00:00+00:00", "book", "betclic", odds=[2.40, 3.20, 3.10]),
        _row("2026-11-02T12:12:00+00:00", "book", "betclic", odds=[2.40, 3.20, 3.10]),
    ]
    report = measure_lag(rows)
    assert report["sharp"]["n_followed"] == 0
    assert report["sharp"]["n_censored"] == 1
    assert report["sharp"]["median_s"] is None


def test_median_de_huit_suivis():
    rows = []
    delays = [60, 120, 180, 240, 300, 360, 420, 480]
    for index, delay in enumerate(delays):
        start = datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc) + timedelta(hours=index)
        moved = start + timedelta(minutes=6)
        followed = moved + timedelta(seconds=delay)
        home = f"Home{index}"
        away = f"Away{index}"
        kick = (start + timedelta(hours=5)).isoformat()
        rows.append(
            {
                "at": start.isoformat(),
                "kind": "sharp",
                "source": "matchbook",
                "home": home,
                "away": away,
                "kickoff": kick,
                "odds": None,
                "probs": [0.40, 0.30, 0.30],
            }
        )
        rows.append(
            {
                "at": moved.isoformat(),
                "kind": "sharp",
                "source": "matchbook",
                "home": home,
                "away": away,
                "kickoff": kick,
                "odds": None,
                "probs": [0.46, 0.27, 0.27],
            }
        )
        rows.append(
            {
                "at": start.isoformat(),
                "kind": "book",
                "source": "betclic",
                "home": home,
                "away": away,
                "kickoff": kick,
                "odds": [2.40, 3.20, 3.10],
                "probs": None,
            }
        )
        rows.append(
            {
                "at": followed.isoformat(),
                "kind": "book",
                "source": "betclic",
                "home": home,
                "away": away,
                "kickoff": kick,
                "odds": [2.20, 3.40, 3.40],
                "probs": None,
            }
        )
    report = measure_lag(rows)
    assert report["sharp"]["n_moves"] == 8
    assert report["sharp"]["n_followed"] == 8
    assert report["sharp"]["median_s"] == 270
    assert report["too_small"] is False
