"""Ligne de commande : relevé, sonde, rien d'automatique côté paris."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from grotonome.alertes import remember_alerts, select_alerts
from grotonome.fraicheur import remember_betclic_fair
from grotonome.history import append_rows, changed_rows, french_clv, snapshot_rows
from grotonome.journal import attach_closes, load_jsonl, performance, record, settle, write_jsonl
from grotonome.pipeline import analyze
from grotonome.render import alert_text, dumps, payload, telegram_text
from grotonome.results import fetch_results
from grotonome.sources.fetch import fetch_all, price_pinnacle, price_smarkets
from grotonome.telegram import send_message

PARIS = ZoneInfo("Europe/Paris")
CLOSE_WINDOW = timedelta(minutes=15)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="grotonome")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="relever les cotes et écrire la page")
    run.add_argument("--out", default="site")
    run.add_argument("--journal", default="data/journal.jsonl")
    run.add_argument("--sharp", default="data/sharp.jsonl")
    run.add_argument("--cotes", default="data/cotes.jsonl")
    run.add_argument("--no-results", action="store_true")
    run.add_argument("--no-telegram", action="store_true")
    run.add_argument("--state", default="data/veille.json")
    passage = sub.add_parser("passage", help="un relevé de la veille continue")
    passage.add_argument("--out", default="site")
    passage.add_argument("--journal", default="data/journal.jsonl")
    passage.add_argument("--sharp", default="data/sharp.jsonl")
    passage.add_argument("--cotes", default="data/cotes.jsonl")
    passage.add_argument("--state", default="data/veille.json")
    passage.add_argument("--no-results", action="store_true")
    passage.add_argument("--no-telegram", action="store_true")
    veille = sub.add_parser("veille", help="boucle de relevés")
    veille.add_argument("--minutes", type=float, default=300)
    veille.add_argument("--interval", type=float, default=360)
    veille.add_argument("--out", default="site")
    veille.add_argument("--journal", default="data/journal.jsonl")
    veille.add_argument("--sharp", default="data/sharp.jsonl")
    veille.add_argument("--cotes", default="data/cotes.jsonl")
    veille.add_argument("--state", default="data/veille.json")
    sub.add_parser("sonde", help="mesurer les sources sans écrire de pari")
    args = parser.parse_args(argv)
    if args.command == "sonde":
        return cmd_sonde()
    if args.command == "veille":
        return cmd_veille(args)
    if args.command == "passage":
        return cmd_passage(args)
    return cmd_run(args)


def cmd_sonde() -> int:
    reports = fetch_all()
    for report in reports:
        state = "ok" if report.ok else "échec"
        print(f"{report.source:16} {state:6} n={report.n:<4} {report.elapsed_s:6.2f}s  {report.detail}")
    return 0


def pause_seconds(elapsed: float, interval: float) -> float:
    return max(0.0, interval - elapsed)


def cmd_veille(args) -> int:
    deadline = time.monotonic() + args.minutes * 60
    while True:
        started = time.monotonic()
        code = cmd_passage(args)
        if code != 0:
            return code
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return 0
        pause = min(pause_seconds(time.monotonic() - started, args.interval), remaining)
        if pause > 0:
            time.sleep(pause)


def cmd_passage(args) -> int:
    now = datetime.now(timezone.utc)
    state = _load_state(Path(args.state))
    backoff = state.setdefault("recul", {})
    ring = state.setdefault("rythme", [])
    ring.append(now.isoformat())
    del ring[:-24]
    print(f"RYTHME {now.isoformat()}", flush=True)
    reports = fetch_all(now=now, backoff=backoff)
    result = analyze(reports, pricer=_price, prior=state.get("etat"))
    _persist_passage(args, result, state, now)
    return 0


def _persist_passage(args, result, state: dict, now: datetime) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    journal = load_jsonl(Path(args.journal))
    record(journal, result.proposals, now=now)
    near = [
        snap
        for snap in result.sharp_snapshots
        if _near_kickoff(snap, now)
    ]
    history = load_jsonl(Path(args.sharp))
    history.extend(near)
    attach_closes(journal, history, window=CLOSE_WINDOW)
    note = "résultats non demandés"
    if not getattr(args, "no_results", False):
        try:
            results, note = fetch_results(Path("data/cache"), day=now.date())
            settle(journal, results)
        except Exception:
            note = "résultats indisponibles"
    fresh = snapshot_rows(result.reports, result.sharp_prices)
    deltas, state["etat"] = changed_rows(state.setdefault("etat", {}), fresh)
    remember_betclic_fair(state["etat"], result.betclic_anchors, deltas)
    append_rows(Path(args.cotes), deltas)
    bankroll = _bankroll()
    alerts = []
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not getattr(args, "no_telegram", False) and token and chat:
        memory = state.setdefault("alertes", {})
        alerts = select_alerts(result.proposals, memory)[:8]
        sent_ok = []
        for bet in alerts:
            if _send(alert_text(bet, bankroll=bankroll)):
                sent_ok.append(bet)
        remember_alerts(memory, sent_ok)
        if _recap_due(state, now) and _send(telegram_text(result, now=now, bankroll=bankroll)):
            state["dernier_recap"] = now.astimezone(PARIS).date().isoformat()
    body = payload(result, now=now, performance=performance(journal), bankroll=bankroll)
    body["performance"]["results_note"] = note
    (out / "latest.json").write_text(dumps(body) + "\n", encoding="utf-8")
    write_jsonl(Path(args.journal), journal)
    write_jsonl(Path(args.sharp), history)
    _save_state(Path(args.state), state)
    print(
        f"passage {now.isoformat()} changements={len(deltas)} alertes={len(alerts)} {note}",
        flush=True,
    )


def _near_kickoff(snap: dict, now: datetime) -> bool:
    try:
        kickoff = datetime.fromisoformat(snap["kickoff"])
    except (KeyError, ValueError):
        return False
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)
    return kickoff - CLOSE_WINDOW <= now < kickoff


def _recap_due(state: dict, now: datetime) -> bool:
    local = now.astimezone(PARIS)
    if local.hour < 8:
        return False
    return state.get("dernier_recap") != local.date().isoformat()


def _send(text: str) -> bool:
    sent, detail = send_message(
        text,
        os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        os.environ.get("TELEGRAM_CHAT_ID", ""),
    )
    print(f"telegram : {detail}", flush=True)
    return sent


def _load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cmd_run(args) -> int:
    now = datetime.now(timezone.utc)
    reports = fetch_all(now=now)
    result = analyze(reports, pricer=_price)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    journal_path = Path(args.journal)
    sharp_path = Path(args.sharp)
    journal = load_jsonl(journal_path)
    record(journal, result.proposals, now=now)
    history = load_jsonl(sharp_path)
    history.extend(result.sharp_snapshots)
    attach_closes(journal, history)
    note = "résultats non demandés"
    if not args.no_results:
        try:
            results, note = fetch_results(Path("data/cache"), day=now.date())
            settle(journal, results)
        except Exception:
            note = "résultats indisponibles"
    stats = performance(journal)
    stats["results_note"] = note
    bankroll = _bankroll()
    body = payload(result, now=now, performance=stats, bankroll=bankroll)
    (out / "latest.json").write_text(dumps(body) + "\n", encoding="utf-8")
    write_jsonl(journal_path, journal)
    write_jsonl(sharp_path, history)
    tape_path = Path(args.cotes)
    fresh = snapshot_rows(result.reports, result.sharp_prices)
    append_rows(tape_path, fresh)
    clv = french_clv(load_jsonl(tape_path))
    print(
        "historique cotes :"
        f" {len(fresh)} lignes ajoutées, CLV FR n={clv['n']}"
        + (f" moyenne={clv['clv_mean']:.4f}" if clv["clv_mean"] is not None else " (pas encore deux instants)")
    )
    text = telegram_text(result, now=now, bankroll=bankroll)
    print(text)
    print(f"résultats : {note}")
    if not args.no_telegram:
        sent, detail = send_message(
            text,
            os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            os.environ.get("TELEGRAM_CHAT_ID", ""),
        )
        print(f"telegram : {detail if sent else detail}")
    return 0


def _price(stub):
    if stub.source == "pinnacle":
        return price_pinnacle(stub)
    return price_smarkets(
        stub.external_id,
        f"{stub.home} vs {stub.away}",
        stub.kickoff,
        stub.captured_at,
    )


def _bankroll() -> float | None:
    raw = os.environ.get("BANKROLL_EUR", "").strip()
    if not raw:
        return None
    try:
        value = float(raw.replace(",", "."))
    except ValueError:
        return None
    return value if value > 0 else None


if __name__ == "__main__":
    sys.exit(main())
