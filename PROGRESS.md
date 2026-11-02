# PROGRESS

## Fait

- Mesure des sources le 2 novembre 2026 depuis la VM, sans contournement. Détail dans `docs/FAISABILITE.md`.
- Unibet.fr, PMU et Netbet (page partielle) renvoient des 1N2. Smarkets et Pinnacle servent de référence sharp. Winamax, Betclic, Olybet, Betsson, Genybet : accès refusé. Unibet.fr est instable (200 puis 403).
- Sonde GitHub Actions `41373331498` : PMU 78 matchs, Netbet 30, Smarkets 215, Matchbook 13, Unibet 403. Pinnacle a répondu ; les noms et le moneyline ont été branchés ensuite.
- Contrôle historique Bet365 contre Pinnacle, ouverture puis clôture, découpage au 1er juillet 2024. CLV de test négative. Détail dans `docs/RECHERCHE.md`.
- Moteur : retrait de marge, EV, quart de Kelly plafonné, appariement, pipeline qui isole une source en panne, journal, CLV, ROI, intervalle à partir de 2 valeurs.
- 33 tests, une commande : `python3 -m pytest`.
- Page mobile `site/`, workflows Tests, Quotidien, Sonde. Mode dégradé sans secrets.

## En cours

- Rien côté code. GitHub Pages n'est pas activé : le déploiement [41373704098](https://github.com/Matttgic/Grotonome/actions/runs/41373704098) a répondu 404. Le propriétaire doit choisir « GitHub Actions » dans Settings → Pages.

## Prochaine étape

- Activer Pages, puis lancer le workflow Quotidien (ou attendre 11:00 UTC).
- Laisser le journal accumuler des CLV avant de reparler d'un avantage sur les books français. L'historique disponible ne le montre pas.

## Décisions

- Références : milieu Smarkets et cote Pinnacle, marge retirée par la méthode puissance (légèrement meilleur Brier sur l'entraînement, écart minuscule). Désaccord de plus de 8 points : pari écarté.
- Books proposés : Unibet.fr, PMU, Netbet. Pas le flux Kambi `ub`, qui n'est pas Unibet.fr.
- Pas de modèle de score, pas de totaux, pas de boosts inventés, pas de chasse aux lignes mortes.
- Toute EV strictement positive est listée, avec l'avertissement historique. Aucun seuil « gagnant » n'est retenu.
- Mise : quart de Kelly, plafond 1,5 %. ROI de suivi à mise unitaire.
- Deux passages par jour pour rester dans le quota gratuit d'une éventuelle clé Odds API.
- Pas de clé Pinnacle à créer : la liste publique des matchs suffit. The Odds API reste facultative.

## Skills et outils externes

- Lecture des sites et API publiques par HTTP depuis la VM (pas de proxy, pas de Bright Data : un proxy aurait contourné le géoblocage, ce qui est exclu).
- football-data.co.uk pour l'historique, non versionné.
- Le scan Opsera interactif n'a pas été lancé : l'outil exige une confirmation de paramètres que ce passage autonome ne peut pas collecter. Contrôle local : pas de jeton dans le dépôt.
- Pytest. GitHub Actions prévu pour les tests, le relevé et Pages.
