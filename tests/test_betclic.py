"""Betclic via la page publique SportyTrader, et le nom commun Unibet / Parions."""

from datetime import datetime, timedelta, timezone

from grotonome.render import _book
from grotonome.sources.parse import (
    clock_offset,
    parse_sporty_betclic_odds,
    parse_sporty_league,
)

NOW = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)

LEAGUE = """
<div data-navigation-url-value="/cotes/lorient-brest-8532705/" class="card">
  02 nov. - 14:45
  <a href="/cotes/lorient-brest-8532705/">Lorient - Brest</a>
</div>
"""

MATCH = """
<img alt="Betclic" src="/betclic.webp">
<span class="pastille--cotes">2.35</span>
<span class="pastille--cotes">3.10</span>
<span class="pastille--cotes">2.83</span>
<img alt="Winamax">
"""


def test_cotes_betclic_1n2():
    assert parse_sporty_betclic_odds(MATCH) == (2.35, 3.10, 2.83)
    assert parse_sporty_betclic_odds("<img alt=\"Winamax\"><span class=\"pastille--cotes\">1.5</span>") is None


def test_horloge_calee_sur_une_heure_connue():
    cards = parse_sporty_league(LEAGUE, today=NOW, competition="ligue 1")
    assert len(cards) == 1
    assert cards[0].home == "Lorient"
    assert cards[0].naive == datetime(2026, 11, 2, 14, 45)
    # 14:45 affiché, 19:45 UTC réel : l'écart mesuré ce jour-là depuis l'Ohio.
    offset = clock_offset(
        cards,
        [("Lorient", "Brest", datetime(2026, 11, 2, 19, 45, tzinfo=timezone.utc))],
    )
    assert offset == timedelta(hours=5)
    assert cards[0].naive.replace(tzinfo=timezone.utc) + offset == datetime(
        2026, 11, 2, 19, 45, tzinfo=timezone.utc
    )


def test_horloge_non_calee_si_aucun_match_commun():
    cards = parse_sporty_league(LEAGUE, today=NOW, competition="ligue 1")
    assert clock_offset(cards, [("Nice", "Lille", datetime(2026, 11, 2, 19, 45, tzinfo=timezone.utc))]) is None


def test_unibet_et_parions_un_seul_nom():
    assert _book("unibet") == "Unibet / Parions Sport"
    assert _book("betclic") == "Betclic"
