"""Téléchargements. Une ligue ou une source en échec n'arrête pas les autres."""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

from grotonome.http import HttpError, get_json, get_text
from grotonome.models import FetchReport, SharpPrice
from grotonome.sources.parse import (
    NETBET_PAGES,
    PMU_PATHS,
    parse_matchbook_events,
    parse_netbet_html,
    parse_pinnacle_matchups,
    parse_pinnacle_moneyline,
    parse_pmu_payload,
    parse_smarkets_quotes,
    parse_unibet_page,
    unibet_competitions,
)

UNIBET_HOME = "https://www.unibet.fr/"
UNIBET_EPT = (
    "https://www.unibet.fr/lvs-api/ept?originId=3&lineId=1&up=1&hidden=0"
    "&liveCount=e&preCount=e&status=OPEN,SUSPENDED"
    "&clockStatus=NOT_STARTED,STARTED,PAUSED,END_OF_PERIOD,ADJUST,INTERMISSION"
    "&includeAllMarkets=1"
)
KAMBI = "https://eu-offering-api.kambicdn.com/offering/v2018/pmusportsfr/listView/{path}.json"
SMARKETS_EVENTS = (
    "https://api.smarkets.com/v3/events/?state=upcoming&type_domain=football"
    "&type_scope=single_event&limit=50&sort=start_datetime,id"
)
MATCHBOOK = (
    "https://api.matchbook.com/edge/rest/events?sport-ids=15&per-page=40"
    "&odds-type=DECIMAL&include-prices=true&price-depth=1&states=open"
    "&interval=next-72-hours"
)
PROBES = {
    "winamax": "https://www.winamax.fr/",
    "betclic": "https://www.betclic.fr/",
    "olybet": "https://www.olybet.fr/",
    "betsson": "https://betsson.fr/",
    "genybet": "https://sport.genybet.fr/",
    "vbet": "https://www.vbet.fr/",
}


def fetch_all(*, sleep: float = 0.35, now: datetime | None = None) -> list[FetchReport]:
    moment = now or datetime.now(timezone.utc)
    reports = [
        _guard("unibet", "book", lambda: fetch_unibet(captured_at=moment, sleep=sleep)),
        _guard("pmu", "book", lambda: fetch_pmu(captured_at=moment, sleep=sleep)),
        _guard("netbet", "book", lambda: fetch_netbet(captured_at=moment, sleep=sleep)),
        _guard("smarkets", "sharp", lambda: fetch_smarkets(captured_at=moment, sleep=sleep)),
        _guard("matchbook", "sharp", lambda: fetch_matchbook(captured_at=moment)),
        _guard("pinnacle", "sharp", lambda: fetch_pinnacle(captured_at=moment)),
        _guard("the-odds-api", "sharp", lambda: fetch_odds_api(captured_at=moment)),
    ]
    reports.extend(probe_blocked(sleep=sleep))
    return reports


def fetch_unibet(*, captured_at: datetime, sleep: float = 0.35) -> FetchReport:
    started = time.perf_counter()
    home = get_text(UNIBET_HOME, timeout=20)
    token = _hs_token(home)
    if not token:
        return FetchReport(
            "unibet",
            "book",
            False,
            "jeton public absent de la page d'accueil",
            time.perf_counter() - started,
        )
    headers = {
        "X-LVS-HSToken": token,
        "Accept": "application/json",
        "Referer": UNIBET_HOME,
    }
    tree = get_json(UNIBET_EPT, headers=headers, timeout=25)
    comps = unibet_competitions(tree)
    if not comps:
        return FetchReport(
            "unibet",
            "book",
            False,
            "arbre des compétitions vide",
            time.perf_counter() - started,
        )
    events = []
    notes = []
    for key, node_id in comps:
        time.sleep(sleep)
        url = (
            f"https://www.unibet.fr/lvs-api/next/50/p{node_id}"
            "?lineId=1&originId=3&breakdownEventsIntoDays=true&pageIndex=0&showPromotions=true"
        )
        try:
            payload = get_json(url, headers=headers, timeout=25)
        except HttpError as exc:
            notes.append(f"{key}: HTTP {exc.status}")
            continue
        found = parse_unibet_page(payload, competition=key, captured_at=captured_at)
        events.extend(found)
        notes.append(f"{key}: {len(found)}")
    ok = bool(events)
    detail = ", ".join(notes) if notes else "aucune compétition"
    return FetchReport("unibet", "book", ok, detail, time.perf_counter() - started, len(events), events)


def fetch_pmu(*, captured_at: datetime, sleep: float = 0.8) -> FetchReport:
    started = time.perf_counter()
    events = []
    notes = []
    for key, path in PMU_PATHS.items():
        url = KAMBI.format(path=path) + "?lang=fr_FR&market=FR&client_id=2&channel_id=1"
        try:
            payload = get_json(url, timeout=20)
        except HttpError as exc:
            notes.append(f"{key}: HTTP {exc.status}")
            time.sleep(sleep)
            continue
        found = parse_pmu_payload(payload, competition=key, captured_at=captured_at)
        events.extend(found)
        notes.append(f"{key}: {len(found)}")
        time.sleep(sleep)
    detail = ", ".join(notes) if notes else "aucun appel"
    return FetchReport("pmu", "book", bool(events), detail, time.perf_counter() - started, len(events), events)


def fetch_netbet(*, captured_at: datetime, sleep: float = 0.4) -> FetchReport:
    started = time.perf_counter()
    events = []
    notes = []
    for key, url in NETBET_PAGES.items():
        try:
            html = get_text(url, timeout=20)
        except HttpError as exc:
            notes.append(f"{key}: HTTP {exc.status}")
            time.sleep(sleep)
            continue
        found = parse_netbet_html(html, competition=key, captured_at=captured_at)
        events.extend(found)
        notes.append(f"{key}: {len(found)} (page partielle)")
        time.sleep(sleep)
    detail = ", ".join(notes) if notes else "aucune page"
    if events:
        detail += ". Couverture limitée aux matchs présents dans le HTML."
    return FetchReport("netbet", "book", bool(events), detail, time.perf_counter() - started, len(events), events)


def fetch_smarkets(*, captured_at: datetime, sleep: float = 0.3, horizon_hours: int = 72) -> FetchReport:
    started = time.perf_counter()
    horizon = captured_at + timedelta(hours=horizon_hours)
    stubs = []
    url: str | None = SMARKETS_EVENTS
    pages = 0
    error = ""
    try:
        while url and pages < 12:
            payload = get_json(url, timeout=20)
            events = payload.get("events") or []
            if not events:
                break
            for event in events:
                try:
                    kickoff = datetime.fromisoformat(str(event["start_datetime"]).replace("Z", "+00:00"))
                except (KeyError, TypeError, ValueError):
                    continue
                if kickoff > horizon:
                    url = None
                    break
                stubs.append(event)
            pages += 1
            nxt = (payload.get("pagination") or {}).get("next_page")
            if url is None or not nxt:
                break
            url = "https://api.smarkets.com/v3/events/" + nxt
            time.sleep(sleep)
    except HttpError as exc:
        error = f"HTTP {exc.status}"
        if not stubs:
            return FetchReport(
                "smarkets", "sharp", False, f"liste {error}", time.perf_counter() - started
            )
    except Exception as exc:
        error = f"erreur {type(exc).__name__}"
        if not stubs:
            return FetchReport(
                "smarkets", "sharp", False, f"liste {error}", time.perf_counter() - started
            )
    # Les prix sont chargés plus tard, seulement pour les matchs déjà vus chez un book.
    # Ici on garde les noms. Les probabilités sont remplies par price_smarkets.
    sharp = []
    for event in stubs:
        name = event.get("name") or ""
        if " vs " not in name:
            continue
        home, away = name.split(" vs ", 1)
        try:
            kickoff = datetime.fromisoformat(str(event["start_datetime"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        sharp.append(
            SharpPrice(
                source="smarkets",
                competition="",
                home=home.strip(),
                away=away.strip(),
                kickoff=kickoff,
                captured_at=captured_at,
                external_id=str(event.get("id") or ""),
            )
        )
    detail = f"{len(sharp)} matchs listés sur {pages} page(s), prix chargés après appariement"
    if error:
        detail += f", pagination interrompue ({error})"
    return FetchReport(
        "smarkets", "sharp", bool(sharp), detail, time.perf_counter() - started, len(sharp), sharp=sharp
    )


def price_smarkets(event_id: str, event_name: str, kickoff: datetime, captured_at: datetime) -> SharpPrice | None:
    markets = get_json(f"https://api.smarkets.com/v3/events/{event_id}/markets/", timeout=20)
    winner = next(
        (
            m
            for m in markets.get("markets") or []
            if (m.get("market_type") or {}).get("name") == "WINNER_3_WAY"
        ),
        None,
    )
    if winner is None:
        return None
    market_id = winner["id"]
    time.sleep(1.0)
    contracts = get_json(f"https://api.smarkets.com/v3/markets/{market_id}/contracts/", timeout=20)
    time.sleep(1.0)
    quotes = get_json(f"https://api.smarkets.com/v3/markets/{market_id}/quotes/", timeout=20)
    return parse_smarkets_quotes(
        event_name=event_name,
        kickoff=kickoff,
        contracts=contracts.get("contracts") or [],
        quotes=quotes,
        captured_at=captured_at,
    )


def fetch_matchbook(*, captured_at: datetime) -> FetchReport:
    started = time.perf_counter()
    try:
        payload = get_json(MATCHBOOK, timeout=30)
    except HttpError as exc:
        return FetchReport("matchbook", "sharp", False, f"HTTP {exc.status}", time.perf_counter() - started)
    sharp = parse_matchbook_events(payload, captured_at=captured_at)
    detail = f"{len(sharp)} matchs avec liquidité suffisante sur la page reçue"
    return FetchReport(
        "matchbook", "sharp", bool(sharp), detail, time.perf_counter() - started, len(sharp), sharp=sharp
    )


def fetch_pinnacle(*, captured_at: datetime) -> FetchReport:
    """Noms via la liste des matchs, prix seulement après appariement."""
    started = time.perf_counter()
    try:
        payload = get_json(
            "https://guest.api.arcadia.pinnacle.com/0.1/sports/29/matchups",
            headers={"Accept": "application/json"},
            timeout=30,
        )
    except HttpError as exc:
        return FetchReport("pinnacle", "sharp", False, f"HTTP {exc.status}", time.perf_counter() - started)
    stubs = parse_pinnacle_matchups(payload, captured_at=captured_at)
    horizon = captured_at + timedelta(hours=72)
    stubs = [item for item in stubs if captured_at <= item.kickoff <= horizon]
    detail = f"{len(stubs)} matchs nommés sur 72 h, prix après appariement"
    return FetchReport(
        "pinnacle", "sharp", bool(stubs), detail, time.perf_counter() - started, len(stubs), sharp=stubs
    )


def price_pinnacle(stub: SharpPrice) -> SharpPrice | None:
    time.sleep(0.3)
    payload = get_json(
        f"https://guest.api.arcadia.pinnacle.com/0.1/matchups/{stub.external_id}/markets/straight",
        headers={"Accept": "application/json"},
        timeout=20,
    )
    odds = parse_pinnacle_moneyline(payload)
    if odds is None:
        return None
    return SharpPrice(
        source="pinnacle",
        competition=stub.competition,
        home=stub.home,
        away=stub.away,
        kickoff=stub.kickoff,
        captured_at=stub.captured_at,
        odds=odds,
        external_id=stub.external_id,
    )


def fetch_odds_api(*, captured_at: datetime) -> FetchReport:
    key = os.environ.get("ODDS_API_KEY", "").strip()
    if not key:
        return FetchReport(
            "the-odds-api",
            "sharp",
            False,
            "ODDS_API_KEY absente : source inactive (le reste continue)",
            0.0,
        )
    started = time.perf_counter()
    sports = (
        "soccer_france_ligue_one",
        "soccer_epl",
        "soccer_spain_la_liga",
        "soccer_italy_serie_a",
        "soccer_germany_bundesliga",
        "soccer_uefa_champs_league",
    )
    sharp: list[SharpPrice] = []
    notes = []
    for sport in sports:
        url = (
            "https://api.the-odds-api.com/v4/sports/"
            f"{sport}/odds?regions=eu&markets=h2h&oddsFormat=decimal&bookmakers=pinnacle&apiKey={key}"
        )
        try:
            payload = get_json(url, timeout=25)
        except HttpError as exc:
            notes.append(f"{sport}: HTTP {exc.status}")
            continue
        if not isinstance(payload, list):
            notes.append(f"{sport}: format inattendu")
            continue
        count = 0
        for event in payload:
            odds = _pinnacle_h2h(event)
            if odds is None:
                continue
            try:
                kickoff = datetime.fromisoformat(str(event["commence_time"]).replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            sharp.append(
                SharpPrice(
                    source="pinnacle",
                    competition=sport,
                    home=str(event.get("home_team")),
                    away=str(event.get("away_team")),
                    kickoff=kickoff,
                    captured_at=captured_at,
                    odds=odds,
                )
            )
            count += 1
        notes.append(f"{sport}: {count}")
        time.sleep(0.3)
    detail = ", ".join(notes) if notes else "aucun sport"
    return FetchReport(
        "the-odds-api", "sharp", bool(sharp), detail, time.perf_counter() - started, len(sharp), sharp=sharp
    )


def probe_blocked(*, sleep: float = 0.2) -> list[FetchReport]:
    reports = []
    for name, url in PROBES.items():
        started = time.perf_counter()
        try:
            get_text(url, timeout=12)
        except HttpError as exc:
            detail = f"HTTP {exc.status}, pas de contournement"
            if name == "genybet" and exc.status == 403:
                detail = "accès refusé (géoblocage probable), pas de contournement"
            reports.append(FetchReport(name, "probe", False, detail, time.perf_counter() - started))
        except Exception as exc:
            reports.append(
                FetchReport(
                    name,
                    "probe",
                    False,
                    f"erreur {type(exc).__name__}",
                    time.perf_counter() - started,
                )
            )
        else:
            reports.append(
                FetchReport(
                    name,
                    "probe",
                    False,
                    "page ouverte mais aucune cote structurée branchée",
                    time.perf_counter() - started,
                )
            )
        time.sleep(sleep)
    return reports


def _guard(name: str, kind: str, fn) -> FetchReport:
    try:
        return fn()
    except HttpError as exc:
        return FetchReport(name, kind, False, f"HTTP {exc.status}", 0.0)
    except Exception as exc:  # une source cassée ne casse pas le relevé
        return FetchReport(name, kind, False, f"erreur {type(exc).__name__}", 0.0)


def _hs_token(html: str) -> str | None:
    import re

    match = re.search(r'"hsToken"\s*:\s*"([^"]+)"', html)
    return match.group(1) if match else None


def _pinnacle_h2h(event: dict) -> tuple[float, float, float] | None:
    home = event.get("home_team")
    away = event.get("away_team")
    for book in event.get("bookmakers") or []:
        if book.get("key") != "pinnacle":
            continue
        for market in book.get("markets") or []:
            if market.get("key") != "h2h":
                continue
            found = {}
            for outcome in market.get("outcomes") or []:
                name = outcome.get("name")
                price = outcome.get("price")
                if name == home:
                    found["H"] = float(price)
                elif name == away:
                    found["A"] = float(price)
                elif name == "Draw":
                    found["D"] = float(price)
            if set(found) == {"H", "D", "A"} and all(v > 1 for v in found.values()):
                return (found["H"], found["D"], found["A"])
    return None


# Conservé pour les tests de conversion, utilisé si un relevé Pinnacle brut est branché.
__all__ = ["fetch_all", "price_smarkets"]
