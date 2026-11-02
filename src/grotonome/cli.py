"""Ligne de commande : relevé, sonde, rien d'automatique côté paris."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from grotonome.journal import attach_closes, load_jsonl, performance, record, settle, write_jsonl
from grotonome.pipeline import analyze
from grotonome.render import dumps, payload, telegram_text
from grotonome.results import fetch_results
from grotonome.sources.fetch import fetch_all, price_pinnacle, price_smarkets
from grotonome.telegram import send_message


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="grotonome")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="relever les cotes et écrire la page")
    run.add_argument("--out", default="site")
    run.add_argument("--journal", default="data/journal.jsonl")
    run.add_argument("--sharp", default="data/sharp.jsonl")
    run.add_argument("--no-results", action="store_true")
    run.add_argument("--no-telegram", action="store_true")
    sub.add_parser("sonde", help="mesurer les sources sans écrire de pari")
    args = parser.parse_args(argv)
    if args.command == "sonde":
        return cmd_sonde()
    return cmd_run(args)


def cmd_sonde() -> int:
    reports = fetch_all()
    for report in reports:
        state = "ok" if report.ok else "échec"
        print(f"{report.source:16} {state:6} n={report.n:<4} {report.elapsed_s:6.2f}s  {report.detail}")
    return 0


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
