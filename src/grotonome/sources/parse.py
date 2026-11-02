"""Analyse des réponses déjà téléchargées. Aucun appel réseau."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from grotonome.models import SharpPrice, SoftPrice
from grotonome.names import is_draw, same_team, strip_accents

PMU_PATHS = {
    "ligue 1": "football/france/ligue_1",
    "ligue 2": "football/france/ligue_2",
    "premier league": "football/england/premier_league",
    "laliga": "football/spain/la_liga",
    "serie a": "football/italy/serie_a",
    "bundesliga": "football/germany/bundesliga",
    "champions league": "football/champions_league",
}

# Montant Smarkets × 10 000. 10 000 = 1 de devise.
# Un plancher à 20 (200 000) aurait jeté Portland–Houston le 2 novembre :
# la meilleure offre extérieure valait 22 027, soit environ 2,2, et tout le 1N2 tombait.
SMARKETS_MIN_QUANTITY = 10_000
# Matchbook : plancher déjà appliqué dans _matchbook, 20 USD.
MATCHBOOK_MIN_AMOUNT = 20

_CLOSED = {"SUSPENDED", "CLOSED", "SETTLED", "RESULTED", "HIDDEN", "CANCELLED", "VOID", "UNPRICED"}

NETBET_PAGES = {
    "ligue 1": "https://www.netbet.fr/football/france/ligue-1-mcdonald-s-r",
    "premier league": "https://www.netbet.fr/football/angleterre/premier-league",
    "laliga": "https://www.netbet.fr/football/espagne/laliga",
    "serie a": "https://www.netbet.fr/football/italie/serie-a",
}


def parse_unibet_kickoff(raw: str) -> datetime:
    """Heure compacte `aammjjHHMM` lue en UTC.

    Preuve du 2 novembre 2026, Lorient–Brest : le code `2611021945` coïncide
    avec 19:45Z chez PMU et Smarkets, et avec 20:45+01 chez Netbet. Lu comme
    heure de Paris, il vaudrait 18:45Z et ne collerait à aucune de ces trois sources.
    """
    text = str(raw)
    if len(text) == 10 and text.isdigit():
        year = 2000 + int(text[0:2])
        return datetime(
            year,
            int(text[2:4]),
            int(text[4:6]),
            int(text[6:8]),
            int(text[8:10]),
            tzinfo=timezone.utc,
        )
    return _parse_iso(text)


def competition_key(desc: str) -> str | None:
    name = strip_accents(desc).lower().replace("'", " ")
    if any(
        tag in name
        for tag in (
            "women",
            "woman",
            "feminin",
            "femme",
            "dames",
            "frauen",
            "ladies",
            "femenin",
            "femminile",
            "u17",
            "u18",
            "u19",
            "u20",
            "u21",
            "u23",
            "youth",
            "reserve",
        )
    ):
        return None
    if "conference" in name:
        return "conference league"
    if "europa" in name:
        return "europa league"
    # « champion » seul attrapait Championship, Championnat et European Championship.
    if "champions league" in name or "ligue des champions" in name:
        return "champions league"
    if "ligue 2" in name:
        return "ligue 2"
    if "ligue 1" in name:
        return "ligue 1"
    if "premier league" in name:
        return "premier league"
    if "laliga" in name or "la liga" in name:
        if "2" in name:
            return None
        return "laliga"
    if "serie a" in name and "serie b" not in name:
        if any(tag in name for tag in ("brasileir", "brazil", "brasil")):
            return None
        return "serie a"
    if "bundesliga" in name and "2" not in name:
        return "bundesliga"
    return None


def unibet_competitions(tree: dict) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []

    def walk(node: dict, in_football: bool) -> None:
        desc = str(node.get("desc") or "")
        code = str(node.get("code") or "")
        here = in_football or desc == "Football" or code == "FOOT"
        key = competition_key(desc) if here else None
        node_id = node.get("id")
        if key and node_id is not None and not node.get("path"):
            found.append((key, str(node_id)))
        elif key and node_id is not None and node.get("path"):
            # Une compétition peut elle-même contenir des sous-nœuds (phases).
            # On garde le nœud dont le nom est la compétition et qui n'a pas
            # d'enfant portant le même libellé de compétition.
            child_keys = [competition_key(str(c.get("desc") or "")) for c in node["path"]]
            if key not in child_keys:
                found.append((key, str(node_id)))
        for child in node.get("path") or []:
            if isinstance(child, dict):
                walk(child, here)

    for sport in tree.get("ept") or []:
        if isinstance(sport, dict):
            walk(sport, False)
    # Premier identifiant pour chaque clé.
    unique: dict[str, str] = {}
    for key, node_id in found:
        unique.setdefault(key, node_id)
    return list(unique.items())


def parse_unibet_page(payload: dict, *, competition: str, captured_at: datetime) -> list[SoftPrice]:
    items = payload.get("items") or {}
    events = {k: v for k, v in items.items() if str(k).startswith("e")}
    markets = {k: v for k, v in items.items() if str(k).startswith("m")}
    outcomes = {k: v for k, v in items.items() if str(k).startswith("o")}
    by_market: dict[str, list] = {}
    for outcome in outcomes.values():
        by_market.setdefault(str(outcome.get("parent")), []).append(outcome)
    prices: list[SoftPrice] = []
    for event_id, event in events.items():
        home, away = event.get("a"), event.get("b")
        if not home or not away:
            continue
        market = next(
            (
                m
                for m in markets.values()
                if m.get("parent") == event_id and str(m.get("style")) == "WIN_DRAW_WIN"
            ),
            None,
        )
        if market is None:
            continue
        market_id = next(k for k, m in markets.items() if m is market)
        raw_outcomes = by_market.get(market_id, [])
        if any(_blocked_outcome(outcome) for outcome in raw_outcomes):
            # Une issue suspendue : on ne publie pas les deux autres comme un 1N2.
            continue
        try:
            odds = _order_1x2(home, away, raw_outcomes, price_key="price", comma=True)
        except ValueError:
            continue
        prices.append(
            SoftPrice(
                source="unibet",
                competition=competition,
                home=str(home),
                away=str(away),
                kickoff=parse_unibet_kickoff(str(event.get("start"))),
                odds=odds,
                captured_at=captured_at,
            )
        )
    return prices


def parse_pmu_payload(payload: dict, *, competition: str, captured_at: datetime) -> list[SoftPrice]:
    prices: list[SoftPrice] = []
    for item in payload.get("events") or []:
        try:
            event = item.get("event") or {}
            state = str(event.get("state") or "")
            if state in {"STARTED", "FINISHED", "CLOSED", "SETTLED"}:
                continue
            home, away = event.get("homeName"), event.get("awayName")
            if not home or not away:
                continue
            offer = next(
                (
                    o
                    for o in item.get("betOffers") or []
                    if (o.get("criterion") or {}).get("englishLabel") == "Full Time"
                    and (o.get("betOfferType") or {}).get("englishName") == "Match"
                ),
                None,
            )
            if offer is None:
                continue
            outcomes = offer.get("outcomes") or []
            ordered = _order_pmu(str(home), str(away), outcomes)
            changed = [_parse_iso(o["changedDate"]) for o in outcomes if o.get("changedDate")]
            # Le dernier mouvement est le plus récent, pas le plus ancien.
            movement = max(changed) if changed else None
            kickoff = _parse_iso(str(event.get("start")))
        except (TypeError, ValueError, KeyError, OverflowError):
            continue
        prices.append(
            SoftPrice(
                source="pmu",
                competition=competition,
                home=str(home),
                away=str(away),
                kickoff=kickoff,
                odds=ordered,
                captured_at=captured_at,
                movement_at=movement,
            )
        )
    return prices


def parse_netbet_html(html: str, *, competition: str, captured_at: datetime) -> list[SoftPrice]:
    text = _unescape_js(html)
    pattern = re.compile(
        r'label:"([^"]{2,40}) / ([^"]{2,40})",url:"[^"]*",(?:(?!start:").){0,700}start:"([^"]+)"',
        re.S,
    )
    seen: set[tuple[str, str, str]] = set()
    prices: list[SoftPrice] = []
    for match in pattern.finditer(text):
        home, away, start = match.group(1), match.group(2), match.group(3)
        key = (home, away, start)
        if key in seen:
            continue
        seen.add(key)
        window = text[match.start() : match.start() + 2500]
        # « Qui va gagner » tout court attrape aussi la mi-temps ou un autre marché.
        marker = window.find("Qui va gagner le match")
        chunk = window[marker : marker + 2200] if marker >= 0 else ""
        pairs = []
        for found in re.finditer(r'actorLabel:"([^"]+)"\},oddsDisplay:"([0-9.]*)"', chunk):
            context = chunk[max(0, found.start() - 400) : found.end()]
            if re.search(r"suspend", context, re.I):
                continue
            if not found.group(2):
                continue
            pairs.append((found.group(1), found.group(2)))
        if len(pairs) < 3:
            continue
        try:
            odds = _triples(home, away, pairs[:3])
            kickoff = _parse_iso(start)
        except ValueError:
            continue
        prices.append(
            SoftPrice(
                source="netbet",
                competition=competition,
                home=home,
                away=away,
                kickoff=kickoff,
                odds=odds,
                captured_at=captured_at,
            )
        )
    return prices


def parse_winamax_html(html: str, *, captured_at: datetime) -> list[SoftPrice]:
    """État préchargé de la page publique paris-sportifs. Pas d'appel de plus."""
    marker = html.find("PRELOADED_STATE")
    if marker < 0:
        return []
    start = html.find("{", marker)
    if start < 0:
        return []
    try:
        import json

        data, _end = json.JSONDecoder().raw_decode(html[start:])
    except json.JSONDecodeError:
        return []
    matches = data.get("matches") or {}
    bets = data.get("bets") or {}
    outcomes = data.get("outcomes") or {}
    odds_map = data.get("odds") or {}
    tournaments = data.get("tournaments") or {}
    prices: list[SoftPrice] = []
    for match in matches.values():
        if match.get("sportId") != 1 or match.get("status") != "PREMATCH":
            continue
        home, away = match.get("competitor1Name"), match.get("competitor2Name")
        if not home or not away:
            continue
        bet = bets.get(str(match.get("mainBetId"))) or bets.get(match.get("mainBetId"))
        if not bet or not bet.get("available", True):
            continue
        title = str(bet.get("betTitle") or bet.get("betTypeName") or "")
        if title not in {"Résultat", "1X2", "Résultat du match"}:
            continue
        found: dict[str, float] = {}
        suspended = False
        for outcome_id in bet.get("outcomes") or []:
            outcome = outcomes.get(str(outcome_id)) or outcomes.get(outcome_id) or {}
            if outcome.get("available") is False:
                suspended = True
                break
            raw = odds_map.get(str(outcome_id), odds_map.get(outcome_id))
            try:
                odds = float(raw)
            except (TypeError, ValueError):
                suspended = True
                break
            code = str(outcome.get("code") or "").lower()
            label = str(outcome.get("label") or "")
            if code == "1" or label == home:
                found["H"] = odds
            elif code in {"x", "n"} or is_draw(label):
                found["D"] = odds
            elif code == "2" or label == away:
                found["A"] = odds
        if suspended or set(found) != {"H", "D", "A"} or any(o <= 1 for o in found.values()):
            continue
        try:
            kickoff = datetime.fromtimestamp(int(match["matchStart"]), tz=timezone.utc)
        except (KeyError, TypeError, ValueError, OSError, OverflowError):
            continue
        tour = tournaments.get(str(match.get("tournamentId"))) or tournaments.get(match.get("tournamentId")) or {}
        prices.append(
            SoftPrice(
                source="winamax",
                competition=str(tour.get("tournamentName") or ""),
                home=str(home),
                away=str(away),
                kickoff=kickoff,
                odds=(found["H"], found["D"], found["A"]),
                captured_at=captured_at,
            )
        )
    return prices


def parse_smarkets_quotes(
    *,
    event_name: str,
    kickoff: datetime,
    contracts: list[dict],
    quotes: dict,
    captured_at: datetime,
) -> SharpPrice | None:
    if " vs " not in event_name:
        return None
    home, away = event_name.split(" vs ", 1)
    by_role: dict[str, float] = {}
    for contract in contracts:
        role = ((contract.get("contract_type") or {}).get("name") or "").upper()
        if role not in {"HOME", "DRAW", "AWAY"}:
            continue
        quote = quotes.get(str(contract.get("id"))) or quotes.get(contract.get("id")) or {}
        bids = quote.get("bids") or []
        offers = quote.get("offers") or []
        if not bids or not offers:
            return None
        bid = bids[0]["price"] / 10000
        offer = offers[0]["price"] / 10000
        if offer < bid or not 0 < bid < 1 or not 0 < offer < 1:
            return None
        if offer - bid > 0.10:
            return None
        # quantity est le montant disponible × 10 000 (doc Smarkets). 200 000 = 20.
        # Un carnet minuscule ne fixe pas la probabilité juste. Quantité absente : on refuse.
        bid_qty = bids[0].get("quantity")
        offer_qty = offers[0].get("quantity")
        if bid_qty is None or offer_qty is None:
            return None
        if float(bid_qty) < SMARKETS_MIN_QUANTITY or float(offer_qty) < SMARKETS_MIN_QUANTITY:
            return None
        by_role[role] = (bid + offer) / 2
    if set(by_role) != {"HOME", "DRAW", "AWAY"}:
        return None
    return SharpPrice(
        source="smarkets",
        competition="",
        home=home.strip(),
        away=away.strip(),
        kickoff=kickoff,
        captured_at=captured_at,
        probs=(by_role["HOME"], by_role["DRAW"], by_role["AWAY"]),
    )


def parse_matchbook_events(payload: dict, *, captured_at: datetime) -> list[SharpPrice]:
    prices: list[SharpPrice] = []
    moment = _as_utc(captured_at)
    for event in payload.get("events") or []:
        # Un match déjà en jeu n'est pas une référence d'avant-match.
        if event.get("in-running-flag") or event.get("live"):
            continue
        name = str(event.get("name") or "")
        if " vs " not in name:
            continue
        home, away = name.split(" vs ", 1)
        market = next(
            (
                m
                for m in event.get("markets") or []
                if str(m.get("name") or "").lower() in {"match odds", "1x2"}
                and not m.get("live")
            ),
            None,
        )
        if market is None:
            continue
        mids: dict[str, float] = {}
        for runner in market.get("runners") or []:
            label = str(runner.get("name") or "")
            win = _matchbook_side(runner, "win")
            lose = _matchbook_side(runner, "lose")
            if win is None or lose is None:
                continue
            if win[1] < MATCHBOOK_MIN_AMOUNT:
                continue
            p_back = 1 / win[0]
            p_lay = 1 - (1 / lose[0])
            if not 0 < p_back < 1 or not 0 < p_lay < 1:
                continue
            mids[label] = (p_back + p_lay) / 2
        try:
            ordered = (
                _pick_runner(mids, home),
                _pick_runner(mids, "Draw") or _pick_runner(mids, "The Draw"),
                _pick_runner(mids, away),
            )
        except ValueError:
            continue
        if any(p is None for p in ordered):
            continue
        try:
            kickoff = _parse_iso(str(event.get("start")))
        except ValueError:
            continue
        if kickoff < moment:
            continue
        prices.append(
            SharpPrice(
                source="matchbook",
                competition="",
                home=home.strip(),
                away=away.strip(),
                kickoff=kickoff,
                captured_at=captured_at,
                probs=(float(ordered[0]), float(ordered[1]), float(ordered[2])),
            )
        )
    return prices


def _pick_runner(mids: dict[str, float], name: str) -> float | None:
    for label, prob in mids.items():
        if label.lower() == name.lower():
            return prob
    return None


def _matchbook_side(runner: dict, side: str) -> tuple[float, float] | None:
    for price in runner.get("prices") or []:
        if price.get("side") != side:
            continue
        odds = price.get("decimal-odds") or price.get("odds")
        amount = price.get("available-amount") or 0
        try:
            odds_f = float(odds)
            amount_f = float(amount)
        except (TypeError, ValueError):
            return None
        if odds_f <= 1:
            return None
        return odds_f, amount_f
    return None


def _blocked_outcome(outcome: dict) -> bool:
    status = str(outcome.get("status") or outcome.get("state") or "").upper()
    if status in _CLOSED:
        return True
    flags = outcome.get("flags") or []
    if isinstance(flags, str):
        flags = [flags]
    return any(str(flag).lower() in {"suspended", "unpriced", "hidden", "closed"} for flag in flags)


def _order_1x2(home: str, away: str, outcomes: list, *, price_key: str, comma: bool) -> tuple[float, float, float]:
    found: dict[str, float] = {}
    for outcome in outcomes:
        label = str(outcome.get("desc") or outcome.get("label") or "")
        raw = outcome.get(price_key)
        if raw in (None, "", "None"):
            continue
        text = str(raw).replace(",", ".") if comma else str(raw)
        try:
            odds = float(text)
        except ValueError:
            continue
        if odds <= 1:
            continue
        if label == home or label.lower() == "1":
            found["H"] = odds
        elif is_draw(label) or label.upper() == "N":
            found["D"] = odds
        elif label == away or label.lower() == "2":
            found["A"] = odds
    if set(found) != {"H", "D", "A"}:
        raise ValueError("1N2 incomplet")
    return (found["H"], found["D"], found["A"])


def _order_pmu(home: str, away: str, outcomes: list) -> tuple[float, float, float]:
    found: dict[str, float] = {}
    for outcome in outcomes:
        status = outcome.get("status")
        if status not in (None, "OPEN"):
            continue
        label = str(outcome.get("label") or "")
        participant = outcome.get("participant")
        odds = float(outcome["odds"]) / 1000
        if label == "1":
            if participant and not same_team(str(participant), home):
                raise ValueError("domicile PMU incohérent avec le libellé 1")
            found["H"] = odds
        elif label == "X":
            found["D"] = odds
        elif label == "2":
            if participant and not same_team(str(participant), away):
                raise ValueError("extérieur PMU incohérent avec le libellé 2")
            found["A"] = odds
    if set(found) != {"H", "D", "A"} or any(o <= 1 for o in found.values()):
        raise ValueError("1N2 PMU incomplet")
    return (found["H"], found["D"], found["A"])


def _triples(home: str, away: str, pairs: list[tuple[str, str]]) -> tuple[float, float, float]:
    found: dict[str, float] = {}
    for label, raw in pairs:
        odds = float(raw)
        if label == home:
            found["H"] = odds
        elif is_draw(label):
            found["D"] = odds
        elif label == away:
            found["A"] = odds
    if set(found) != {"H", "D", "A"} or any(o <= 1 for o in found.values()):
        raise ValueError("1N2 Netbet incomplet")
    return (found["H"], found["D"], found["A"])


def _unescape_js(text: str) -> str:
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)


def _as_utc(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def _parse_iso(text: str) -> datetime:
    cleaned = text.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_pinnacle_matchups(payload: list, *, captured_at: datetime) -> list[SharpPrice]:
    if not isinstance(payload, list):
        return []
    found: list[SharpPrice] = []
    for item in payload:
        if item.get("type") != "matchup" or item.get("parentId") or item.get("isLive"):
            continue
        names = {}
        for participant in item.get("participants") or []:
            alignment = participant.get("alignment")
            if alignment in {"home", "away"} and participant.get("name"):
                names[alignment] = str(participant["name"])
        if set(names) != {"home", "away"}:
            continue
        try:
            kickoff = _parse_iso(str(item["startTime"]))
        except (KeyError, ValueError):
            continue
        league = item.get("league") or {}
        competition = league.get("name") if isinstance(league, dict) else ""
        found.append(
            SharpPrice(
                source="pinnacle",
                competition=competition or "",
                home=names["home"],
                away=names["away"],
                kickoff=kickoff,
                captured_at=captured_at,
                external_id=str(item.get("id")),
            )
        )
    return found


def parse_pinnacle_moneyline(markets: list) -> tuple[float, float, float] | None:
    if not isinstance(markets, list):
        return None
    chosen = next(
        (
            market
            for market in markets
            if market.get("type") == "moneyline"
            and market.get("period") == 0
            and not market.get("isAlternate")
            and market.get("status") in (None, "open")
        ),
        None,
    )
    if chosen is None:
        return None
    found = {}
    for price in chosen.get("prices") or []:
        side = price.get("designation")
        if side not in {"home", "away", "draw"}:
            continue
        try:
            found[side] = american_to_decimal(price["price"])
        except (KeyError, TypeError, ValueError):
            return None
    if set(found) != {"home", "away", "draw"}:
        return None
    return (found["home"], found["draw"], found["away"])


def american_to_decimal(price: int | float) -> float:
    value = float(price)
    if value >= 100:
        return value / 100 + 1
    if value <= -100:
        return 100 / abs(value) + 1
    raise ValueError(f"cote américaine invalide : {price}")
