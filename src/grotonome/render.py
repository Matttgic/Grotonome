"""Textes affichés sur le téléphone. Aucun chiffre n'est ajouté s'il manque."""

from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from grotonome.models import Proposal
from grotonome.pipeline import RunResult

PARIS = ZoneInfo("Europe/Paris")

HISTORICAL = (
    "Contrôle historique (Bet365 contre Pinnacle, ouverture puis clôture, "
    "saisons 2021-2026, cinq grands championnats, test à partir de juillet 2024) : "
    "au seuil 0 %, n=128, ROI +1,2 %, CLV moyenne −0,6 %, intervalle de confiance "
    "très large et qui contient zéro. Au seuil 2 %, n=27, CLV −4,0 %. "
    "Ce n'est pas un avantage démontré. Bet365 n'est pas un bookmaker ANJ : "
    "c'est un proxy de book « soft », faute d'historique public des cotes françaises."
)


def telegram_text(result: RunResult, *, now: datetime, bankroll: float | None, limit: int = 5) -> str:
    stamp = now.astimezone(PARIS).strftime("%d/%m %H:%M")
    lines = [f"Grotonome — {stamp} (Paris)"]
    shown = result.proposals[:limit]
    if not shown:
        lines.append("Aucun pari à espérance positive.")
    else:
        lines.append(f"{len(shown)} pari(s) à valeur positive" + (f" (sur {len(result.proposals)})" if len(result.proposals) > limit else "") + ".")
        for index, bet in enumerate(shown, start=1):
            lines.append("")
            lines.append(f"{index}. {bet.home} – {bet.away}")
            lines.append(
                f"{_book(bet.bookmaker)} · {bet.selection} · cote {_num(bet.odds)}"
            )
            stake = f"mise {_num(bet.stake_fraction * 100)} % de la bankroll"
            if bankroll:
                stake += f" ({_num(bet.stake_fraction * bankroll)} €)"
            lines.append(f"EV {_signed(bet.ev)} · {stake}")
            lines.append(f"limite {bet.kickoff.astimezone(PARIS).strftime('%d/%m %H:%M')}")
            lines.append(
                f"proba juste {_num(bet.fair_p * 100)} % · {bet.devig} · {', '.join(bet.sharp_sources)}"
            )
            if bet.warnings:
                lines.append("note : " + " ; ".join(bet.warnings))
    lines.append("")
    lines.append(_source_line(result))
    broken = [r for r in result.reports if r.kind != "probe" and not r.ok]
    probes = [r for r in result.reports if r.kind == "probe" and not r.ok]
    if broken:
        lines.append("Références ou books incomplets : " + ", ".join(f"{r.source} ({r.detail})" for r in broken))
    if probes:
        lines.append("Non branchés : " + ", ".join(r.source for r in probes))
    sure = [row for row in result.shopping if row["surebet"]]
    if sure:
        lines.append(f"Surebet entre books français : {len(sure)} (détail sur la page).")
    lines.append("Pas de pari automatique. À placer soi-même, ou pas.")
    return "\n".join(lines)


def payload(result: RunResult, *, now: datetime, performance: dict, bankroll: float | None) -> dict:
    def bet(item: Proposal) -> dict:
        body = {
            "match": f"{item.home} – {item.away}",
            "competition": item.competition,
            "selection": item.selection,
            "bookmaker": item.bookmaker,
            "odds": item.odds,
            "fair_p": item.fair_p,
            "ev": item.ev,
            "stake_fraction": item.stake_fraction,
            "stake_eur": (item.stake_fraction * bankroll) if bankroll else None,
            "kickoff": item.kickoff.astimezone(PARIS).isoformat(),
            "devig": item.devig,
            "overround": item.overround,
            "sharp_sources": list(item.sharp_sources),
            "warnings": list(item.warnings),
            "movement_at": item.movement_at.isoformat() if item.movement_at else None,
        }
        return body

    return {
        "generated_at": now.astimezone(PARIS).isoformat(),
        "devig": result.devig,
        "bankroll_eur": bankroll,
        "bets": [bet(item) for item in result.proposals],
        "skipped": result.skipped[:30],
        "unmatched": result.unmatched,
        "shopping": result.shopping,
        "sources": [
            {
                "name": report.source,
                "kind": report.kind,
                "ok": report.ok,
                "detail": report.detail,
                "events": report.n,
                "elapsed_s": round(report.elapsed_s, 3),
            }
            for report in result.reports
        ],
        "performance": performance,
        "historical_notice": HISTORICAL,
        "notice": "Grotonome ne place aucun pari. Les cotes absentes restent absentes.",
    }


def dumps(body: dict) -> str:
    return json.dumps(body, ensure_ascii=False, indent=2)


def _source_line(result: RunResult) -> str:
    parts = []
    for report in result.reports:
        if report.kind == "probe":
            continue
        state = "ok" if report.ok else "échec"
        parts.append(f"{report.source} {state} ({report.n})")
    return "Sources : " + ", ".join(parts)


def _book(name: str) -> str:
    return {"unibet": "Unibet", "pmu": "PMU", "netbet": "Netbet"}.get(name, name)


def _num(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def _signed(value: float) -> str:
    percent = value * 100
    text = f"{percent:+.1f}".replace(".", ",")
    return text + " %"
