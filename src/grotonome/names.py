"""Appariement des noms d'équipes. Un doute ne produit pas d'appariement."""

from __future__ import annotations

import unicodedata
from difflib import SequenceMatcher

# Le nom court utilisé par un site et le nom long d'un autre.
ALIASES = {
    "paris sg": "paris saint germain",
    "psg": "paris saint germain",
    "paris saint germain": "paris saint germain",
    "olympique de marseille": "marseille",
    "marseille": "marseille",
    "olympique lyonnais": "lyon",
    "lyon": "lyon",
    "as monaco": "monaco",
    "monaco": "monaco",
    "stade rennais": "rennes",
    "rennes": "rennes",
    "stade de reims": "reims",
    "reims": "reims",
    "stade brestois": "brest",
    "brest": "brest",
    "rc lens": "lens",
    "lens": "lens",
    "ogc nice": "nice",
    "nice": "nice",
    "losc": "lille",
    "lille osc": "lille",
    "lille": "lille",
    "as saint etienne": "saint etienne",
    "saint etienne": "saint etienne",
    "fc nantes": "nantes",
    "nantes": "nantes",
    "montpellier hsc": "montpellier",
    "montpellier": "montpellier",
    "toulouse fc": "toulouse",
    "toulouse": "toulouse",
    "rc strasbourg": "strasbourg",
    "strasbourg": "strasbourg",
    "le havre ac": "le havre",
    "le havre": "le havre",
    "angers sco": "angers",
    "angers": "angers",
    "aj auxerre": "auxerre",
    "auxerre": "auxerre",
    "paris fc": "paris fc",
    "stade troyen": "troyes",
    "estac troyes": "troyes",
    "troyes": "troyes",
}

_DROP = {
    "fc",
    "sc",
    "ac",
    "cf",
    "afc",
    "rc",
    "ogc",
    "aj",
    "as",
    "us",
    "sd",
    "cd",
    "de",
    "du",
    "des",
    "the",
    "club",
}

DRAW_LABELS = {"n", "nul", "x", "draw", "match nul", "egalite", "égalité"}


def strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize(name: str) -> str:
    raw = strip_accents(name).lower().replace("&", " ")
    cleaned = []
    for ch in raw:
        cleaned.append(ch if ch.isalnum() else " ")
    tokens = [tok for tok in "".join(cleaned).split() if tok not in _DROP]
    if not tokens:
        tokens = [tok for tok in "".join(cleaned).split()]
    key = " ".join(tokens)
    return ALIASES.get(key, key)


def same_team(left: str, right: str, *, threshold: float = 0.92) -> bool:
    a, b = normalize(left), normalize(right)
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) < 4 or len(b) < 4:
        return False
    return SequenceMatcher(None, a, b).ratio() >= threshold


def is_draw(label: str) -> bool:
    return strip_accents(label).strip().lower() in {strip_accents(x) for x in DRAW_LABELS}
