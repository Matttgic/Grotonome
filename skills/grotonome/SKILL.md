---
name: grotonome
description: Règles du relevé Grotonome — cotes ANJ, référence sharp, aucune cote inventée. À lire avant de modifier le pipeline, les sources ou le backtest.
---

# Grotonome

Outil personnel de comparaison de cotes. Il ne place aucun pari.

- Books proposés : Winamax (page `paris-sportifs`), Unibet.fr, PMU, Netbet. ZEbet et Parions Sport en ligne redirigent vers Unibet.fr : ne pas les compter deux fois. Pas le flux Kambi `ub`.
- Références : Pinnacle (cotes décimales, marge retirée par la méthode puissance) et milieux Smarkets / Matchbook (normalisés, pas de puissance). Désaccord de plus de 8 points : pas de pari.
- Smarkets : quantité minimale 10 000 (montant × 10 000, soit 1 de devise). Matchbook : 20 USD. Une quantité absente n'est pas une cote.
- Heure compacte Unibet `aammjjHHMM` : UTC, vérifié sur Lorient–Brest le 2 novembre 2026.
- `OM` et `OL` sont Marseille et Lyon. Ne pas retirer `fc` avant de lire l'alias (`Paris FC`).
- Une issue suspendue retire le 1N2. Ne pas deviner un statut minifié.
- Historique : `data/cotes.jsonl`, une ligne par cote et par passage. La CLV française exige deux instants. Sinon elle est absente.
- Ne jamais inventer une cote, un résultat ou une performance. Ne jamais committer de jeton.
- Tests : `python3 -m pytest`. Pas de fusion si c'est rouge.
