"""Rejoue le contrôle historique Bet365 contre Pinnacle.

Les CSV viennent de football-data.co.uk. Ils ne sont pas versionnés.
La décision n'utilise que les cotes d'ouverture. La clôture et le résultat
servent seulement à mesurer.

    python scripts/recherche_historique.py --cache data/cache
"""

from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime
from glob import glob
from pathlib import Path

from grotonome.devig import power
from grotonome.http import HttpError, get_text
from grotonome.value import expected_value

DIVISIONS = ("E0", "F1", "SP1", "I1", "D1")
SEASONS = ("2122", "2223", "2324", "2425", "2526")
SPLIT = datetime(2024, 7, 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", default="data/cache")
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    cache = Path(args.cache)
    if args.download:
        download(cache)
    rows = load(cache)
    rows.sort(key=lambda row: row["date"])
    train = [row for row in rows if row["date"] < SPLIT]
    test = [row for row in rows if row["date"] >= SPLIT]
    print(f"matchs {len(rows)} train {len(train)} test {len(test)}")
    if train:
        print(f"train {train[0]['date'].date()} → {train[-1]['date'].date()}")
    if test:
        print(f"test {test[0]['date'].date()} → {test[-1]['date'].date()}")
    print("\nTest, Bet365 ouverture contre Pinnacle ouverture, CLV sur clôture deviguée")
    for threshold in (0.0, 0.02, 0.05):
        summarize(run(test, threshold), f"seuil {threshold:.0%}")
    print("\nTrain, mêmes seuils, non utilisé pour choisir")
    for threshold in (0.0, 0.02, 0.05):
        summarize(run(train, threshold), f"seuil {threshold:.0%}")
    print("\nBrier Pinnacle ouverture")
    print("train puissance", brier(train), "proportionnel", brier(train, proportional=True))
    print("test  puissance", brier(test), "proportionnel", brier(test, proportional=True))
    print("\nToujours le domicile Bet365, test")
    summarize(always_home(test), "domicile")
    print("\nModèle de fréquences passées, écart ≥ 5 points, test")
    summarize(frequency_model(rows), "fréquences")


def download(cache: Path) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    for season in SEASONS:
        for division in DIVISIONS:
            target = cache / f"{division}_{season}.csv"
            url = f"https://www.football-data.co.uk/mmz4281/{season}/{division}.csv"
            try:
                target.write_text(get_text(url, timeout=40), encoding="utf-8")
                print("ok", target.name)
            except HttpError as exc:
                print("échec", target.name, exc.status)


def load(cache: Path) -> list[dict]:
    rows = []
    for path in glob(str(cache / "*.csv")):
        with open(path, newline="", encoding="utf-8-sig") as handle:
            for raw in csv.DictReader(handle):
                parsed = _date(raw.get("Date") or "")
                if parsed is None or raw.get("FTR") not in {"H", "D", "A"}:
                    continue
                opening = _triple(raw, "PSH", "PSD", "PSA")
                soft = _triple(raw, "B365H", "B365D", "B365A")
                closing = _triple(raw, "PSCH", "PSCD", "PSCA")
                if opening is None:
                    continue
                rows.append(
                    {
                        "date": parsed,
                        "div": Path(path).name.split("_")[0],
                        "result": raw["FTR"],
                        "opening": opening,
                        "soft": soft,
                        "closing": closing,
                        "goals": (_num(raw.get("FTHG")), _num(raw.get("FTAG"))),
                    }
                )
    return rows


def run(sample: list[dict], threshold: float) -> list[dict]:
    bets = []
    for row in sample:
        # La clôture ne décide pas. Un match sans clôture reste dans le ROI, sans CLV.
        if row["soft"] is None:
            continue
        fair = power(row["opening"])
        close = power(row["closing"]) if row["closing"] is not None else None
        candidates = []
        for index, side in enumerate("HDA"):
            odds = row["soft"][index]
            ev = expected_value(fair[index], odds)
            if ev <= 0 or ev < threshold:
                continue
            won = row["result"] == side
            candidates.append(
                {
                    "ev": ev,
                    "clv": None if close is None else odds * close[index] - 1,
                    "pnl": (odds - 1) if won else -1,
                }
            )
        if candidates:
            bets.append(max(candidates, key=lambda bet: bet["ev"]))
    return bets


def always_home(sample: list[dict]) -> list[dict]:
    bets = []
    for row in sample:
        if row["soft"] is None:
            continue
        odds = row["soft"][0]
        won = row["result"] == "H"
        clv = None
        if row["closing"] is not None:
            close = power(row["closing"])
            clv = odds * close[0] - 1
        bets.append({"ev": 0, "clv": clv, "pnl": (odds - 1) if won else -1})
    return bets


def frequency_model(rows: list[dict]) -> list[dict]:
    """Fréquences de la division, sans les résultats du jour en cours."""
    rows = sorted(rows, key=lambda row: (row["date"], row["div"]))
    counts: dict[str, list[int]] = {}
    bets = []
    pending_date = None
    pending: list[dict] = []

    def flush() -> None:
        for previous in pending:
            bucket = counts.setdefault(previous["div"], [0, 0, 0])
            bucket[{"H": 0, "D": 1, "A": 2}[previous["result"]]] += 1
        pending.clear()

    for row in rows:
        if pending_date is not None and row["date"] != pending_date:
            flush()
        pending_date = row["date"]
        bucket = counts.setdefault(row["div"], [0, 0, 0])
        total = sum(bucket)
        if row["date"] >= SPLIT and total >= 80 and row["soft"]:
            probs = [count / total for count in bucket]
            fair = power(row["opening"])
            close = power(row["closing"]) if row["closing"] is not None else None
            candidates = []
            for index, side in enumerate("HDA"):
                prob = probs[index]
                if not 0 < prob < 1 or prob - fair[index] < 0.05:
                    continue
                odds = row["soft"][index]
                ev = expected_value(prob, odds)
                if ev <= 0:
                    continue
                won = row["result"] == side
                candidates.append(
                    {
                        "ev": ev,
                        "clv": None if close is None else odds * close[index] - 1,
                        "pnl": (odds - 1) if won else -1,
                    }
                )
            if candidates:
                bets.append(max(candidates, key=lambda bet: bet["ev"]))
        pending.append(row)
    flush()
    return bets


def brier(sample: list[dict], *, proportional: bool = False) -> tuple[float, int]:
    score = 0.0
    count = 0
    for row in sample:
        if proportional:
            raw = [1 / odds for odds in row["opening"]]
            total = sum(raw)
            fair = [value / total for value in raw]
        else:
            fair = power(row["opening"])
        actual = [1 if row["result"] == side else 0 for side in "HDA"]
        score += sum((fair[i] - actual[i]) ** 2 for i in range(3))
        count += 1
    return (score / count if count else math.nan), count


def summarize(bets: list[dict], label: str) -> None:
    if not bets:
        print(f"{label}: aucun pari")
        return
    n = len(bets)
    profit = sum(bet["pnl"] for bet in bets)
    mean = profit / n
    clvs = [bet["clv"] for bet in bets if bet["clv"] is not None]
    clv = sum(clvs) / len(clvs) if clvs else math.nan
    ev = sum(bet["ev"] for bet in bets) / n
    if n >= 2:
        var = sum((bet["pnl"] - mean) ** 2 for bet in bets) / (n - 1)
        if var == 0:
            interval = "non calculé (variance nulle)"
        else:
            se = math.sqrt(var / n)
            low, high = mean - 1.96 * se, mean + 1.96 * se
            interval = f"[{low * 100:.2f} % ; {high * 100:.2f} %]"
    else:
        interval = "non calculé"
    print(
        f"{label}: n={n} ROI={mean * 100:.2f} % CLV={clv * 100:.2f} % "
        f"EV annoncée={ev * 100:.2f} % IC95={interval}"
    )


def _triple(row: dict, home: str, draw: str, away: str):
    values = [_num(row.get(home)), _num(row.get(draw)), _num(row.get(away))]
    if any(value is None or value <= 1 for value in values):
        return None
    return (values[0], values[1], values[2])


def _num(value):
    try:
        if value in (None, ""):
            return None
        return float(value)
    except ValueError:
        return None


def _date(text: str):
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


if __name__ == "__main__":
    main()
