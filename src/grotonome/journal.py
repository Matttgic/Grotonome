"""Journal des paris proposés. La première cote reste celle du suivi."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

from grotonome.metrics import clustered_mean_interval, unit_pnl
from grotonome.models import Proposal
from grotonome.names import normalize


def proposal_id(item: Proposal) -> str:
    day = item.kickoff.astimezone(timezone.utc).date().isoformat()
    return "|".join(
        [
            day,
            normalize(item.home),
            normalize(item.away),
            item.bookmaker,
            str(item.side),
        ]
    )


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    path.write_text(body, encoding="utf-8")


def record(journal: list[dict], proposals: list[Proposal], *, now: datetime) -> list[dict]:
    known = {row["id"] for row in journal}
    for item in proposals:
        ident = proposal_id(item)
        if ident in known:
            continue
        journal.append(
            {
                "id": ident,
                "proposed_at": now.astimezone(timezone.utc).isoformat(),
                "kickoff": item.kickoff.astimezone(timezone.utc).isoformat(),
                "competition": item.competition,
                "home": item.home,
                "away": item.away,
                "side": item.side,
                "selection": item.selection,
                "bookmaker": item.bookmaker,
                "odds": item.odds,
                "fair_p": item.fair_p,
                "devig": item.devig,
                "ev": item.ev,
                "stake_fraction": item.stake_fraction,
                "overround": item.overround,
                "sharp_sources": list(item.sharp_sources),
                "warnings": list(item.warnings),
                "closing_fair_p": None,
                "closing_observed_at": None,
                "result": None,
                "pnl": None,
            }
        )
        known.add(ident)
    return journal


def attach_closes(
    journal: list[dict],
    snapshots: list[dict],
    *,
    window: timedelta = timedelta(minutes=15),
) -> list[dict]:
    """La clôture est le relevé sharp le plus proche du coup d'envoi, dans les 15 minutes.

    Un relevé plus ancien reste dans l'historique, il ne sert pas de clôture.
    """
    for row in journal:
        kickoff = datetime.fromisoformat(row["kickoff"])
        proposed = datetime.fromisoformat(row["proposed_at"])
        candidates = []
        for snap in snapshots:
            if normalize(snap["home"]) != normalize(row["home"]):
                continue
            if normalize(snap["away"]) != normalize(row["away"]):
                continue
            observed = datetime.fromisoformat(snap["observed_at"])
            snap_kick = datetime.fromisoformat(snap["kickoff"])
            if abs((snap_kick - kickoff).total_seconds()) > 3 * 3600:
                continue
            if not (kickoff - window <= observed < kickoff):
                continue
            if observed <= proposed:
                continue
            candidates.append((observed, snap["fair_p"][row["side"]]))
        if not candidates:
            continue
        observed, prob = max(candidates, key=lambda item: item[0])
        row["closing_fair_p"] = prob
        row["closing_observed_at"] = observed.isoformat()
    return journal


def settle(journal: list[dict], results: list[dict]) -> list[dict]:
    """`results` contient home, away, date ISO et result H/D/A. Rien n'est deviné.

    Un coup d'envoi après minuit UTC peut être daté la veille dans le CSV
    (soirée locale) ou le lendemain à Paris. On accepte une date voisine
    seulement si tous les résultats trouvés disent la même chose.
    """
    index: dict[tuple, str] = {}
    for result in results:
        index.setdefault((normalize(result["home"]), normalize(result["away"]), result["date"]), result["result"])
    for row in journal:
        if row.get("result"):
            continue
        codes = []
        for day in _settlement_dates(str(row.get("kickoff") or "")):
            code = index.get((normalize(row["home"]), normalize(row["away"]), day))
            if code in {"H", "D", "A"}:
                codes.append(code)
        if not codes or len(set(codes)) != 1:
            continue
        code = codes[0]
        row["result"] = code
        won = (code == "H" and row["side"] == 0) or (code == "D" and row["side"] == 1) or (
            code == "A" and row["side"] == 2
        )
        row["pnl"] = unit_pnl(float(row["odds"]), won)
    return journal


def _settlement_dates(kickoff: str) -> list[str]:
    try:
        moment = datetime.fromisoformat(kickoff)
    except ValueError:
        return []
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    utc_day = moment.astimezone(timezone.utc).date()
    paris_day = moment.astimezone(ZoneInfo("Europe/Paris")).date()
    days = {utc_day.isoformat(), paris_day.isoformat(), (utc_day - timedelta(days=1)).isoformat()}
    return sorted(days)


def _match_key(row: dict) -> tuple:
    kick = str(row.get("kickoff") or "")
    return (normalize(str(row.get("home") or "")), normalize(str(row.get("away") or "")), kick[:10])


def _groups(journal: list[dict], value_of) -> list[list[float]]:
    buckets: dict[tuple, list[float]] = {}
    order: list[tuple] = []
    for row in journal:
        value = value_of(row)
        if value is None:
            continue
        key = _match_key(row)
        if key not in buckets:
            order.append(key)
            buckets[key] = []
        buckets[key].append(float(value))
    return [buckets[key] for key in order]


def _missing_interval(interval, groups: list[list[float]]) -> str | None:
    if interval.mean is None or interval.low is not None:
        return None
    if interval.n < 2:
        return "moins de 2 paris"
    if len(groups) < 2:
        return "moins de 2 matchs"
    return "variance nulle"


def performance(journal: list[dict]) -> dict:
    settled = _groups(journal, lambda row: row.get("pnl"))

    def _clv(row: dict):
        if row.get("closing_fair_p") is None:
            return None
        return float(row["odds"]) * float(row["closing_fair_p"]) - 1

    clv = _groups(journal, _clv)
    roi = clustered_mean_interval(settled)
    closing = clustered_mean_interval(clv)
    return {
        "n_bets": len(journal),
        "n_settled": roi.n,
        "n_with_clv": closing.n,
        "n_roi_matches": len(settled),
        "n_clv_matches": len(clv),
        "roi": roi.mean,
        "roi_low": roi.low,
        "roi_high": roi.high,
        "roi_note": _missing_interval(roi, settled),
        "clv_mean": closing.mean,
        "clv_low": closing.low,
        "clv_high": closing.high,
        "clv_note": _missing_interval(closing, clv),
        "flat_stake": True,
    }
