#!/usr/bin/env python3
"""Mesure le retard de la cote Betclic lue sur SportyTrader.

Lit ``data/cotes.jsonl`` (une ligne par changement). Pour chaque mouvement
de Pinnacle, Smarkets ou Matchbook, et pour chaque mouvement d'Unibet,
Winamax ou PMU, cherche le délai jusqu'au prochain changement Betclic sur
le même match.

    python3 scripts/retard_betclic.py data/cotes.jsonl

Moins de 8 suivis sharp : l'échantillon est trop petit pour fixer le seuil
autrement que par la valeur prudente du code (2 points de probabilité juste).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from grotonome.fraicheur import MIN_LAG_SAMPLE, measure_lag


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    path = Path(args[0] if args else "data/cotes.jsonl")
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    report = measure_lag(rows)
    print(_text(report, path))
    return 0


def _text(report: dict, path: Path) -> str:
    sharp = report["sharp"]
    books = report["books"]
    lines = [
        f"Fichier {path} : {report['n_rows']} lignes, dont {report['n_betclic']} Betclic.",
        (
            "Mouvements sharp (Pinnacle, Smarkets, Matchbook) : "
            f"{sharp['n_moves']}. Suivis par Betclic : {sharp['n_followed']}. "
            f"Censurés (cote déjà vue, pas de changement ensuite) : {sharp['n_censored']}. "
            f"Sans cote Betclic antérieure : {sharp['n_absent']}."
        ),
        "Retard médian sharp → Betclic : " + _median(sharp["median_s"]) + ".",
        (
            "Mouvements Unibet, Winamax, PMU : "
            f"{books['n_moves']}. Suivis par Betclic : {books['n_followed']}. "
            f"Censurés : {books['n_censored']}. Sans cote Betclic antérieure : {books['n_absent']}."
        ),
        "Retard médian books → Betclic : " + _median(books["median_s"]) + ".",
    ]
    for source, block in report["per_book"].items():
        lines.append(
            f"  {source} : {_compte(block['n_moves'], 'mouvement', 'mouvements')}, "
            f"{_compte(block['n_followed'], 'suivi', 'suivis')}, "
            "médian " + _median(block["median_s"]) + "."
        )
    if report["too_small"]:
        lines.append(
            "Échantillon trop petit : "
            f"{_compte(sharp['n_followed'], 'suivi sharp', 'suivis sharp')}, "
            f"seuil retenu {MIN_LAG_SAMPLE}. Le médian ne fixe pas la limite d'âge."
        )
    else:
        lines.append(
            f"Échantillon suffisant : {sharp['n_followed']} suivis sharp "
            f"(seuil {MIN_LAG_SAMPLE})."
        )
    return "\n".join(lines)


def _compte(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _median(seconds) -> str:
    if seconds is None:
        return "non calculable"
    minutes = seconds / 60
    return f"{minutes:.1f} min ({seconds:.0f} s)"


if __name__ == "__main__":
    sys.exit(main())
