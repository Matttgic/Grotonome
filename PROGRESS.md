# PROGRESS

## Fait

- Mesure des sources le 2 novembre 2026 depuis la VM, sans contournement. Détail dans `docs/FAISABILITE.md`.
- Unibet.fr, PMU et Netbet (page partielle) renvoient des 1N2. Smarkets sert de référence sharp. Pinnacle donne des prix sans noms (401). Winamax, Betclic, Olybet, Betsson, Genybet : accès refusé.
- Contrôle historique Bet365 contre Pinnacle, ouverture puis clôture, découpage au 1er juillet 2024. CLV de test négative. Détail dans `docs/RECHERCHE.md`.
- Moteur : retrait de marge, EV, quart de Kelly plafonné, appariement, pipeline qui isole une source en panne, journal, CLV, ROI, intervalle à partir de 2 valeurs.
- 33 tests, une commande : `python3 -m pytest`.
- Page mobile `site/`, workflows Tests, Quotidien, Sonde. Mode dégradé sans secrets.

## En cours

- Comparer la sonde VM à un runner GitHub Actions (workflow `Sonde`), puis noter l'écart dans `docs/FAISABILITE.md` si l'accès diffère.

## Prochaine étape

- Premier relevé réel sur `main` (workflow Quotidien) une fois Pages et, si voulu, Telegram configurés par le propriétaire.
- Laisser le journal accumuler des CLV avant de reparler d'un avantage sur les books français. L'historique disponible ne le montre pas.

## Décisions

- Référence par défaut : milieu Smarkets, marge retirée par la méthode puissance (légèrement meilleur Brier sur l'entraînement, écart minuscule).
- Books proposés : Unibet.fr, PMU, Netbet. Pas le flux Kambi `ub`, qui n'est pas Unibet.fr.
- Pas de modèle de score, pas de totaux, pas de boosts inventés, pas de chasse aux lignes mortes.
- Toute EV strictement positive est listée, avec l'avertissement historique. Aucun seuil « gagnant » n'est retenu.
- Mise : quart de Kelly, plafond 1,5 %. ROI de suivi à mise unitaire.
- Deux passages par jour pour rester dans le quota gratuit d'une éventuelle clé Odds API.
- Pinnacle direct laissé inactif : prix sans noms. Pas de clé Pinnacle à créer.

## Skills et outils externes

- Lecture des sites et API publiques par HTTP depuis la VM (pas de proxy, pas de Bright Data : un proxy aurait contourné le géoblocage, ce qui est exclu).
- football-data.co.uk pour l'historique, non versionné.
- Le scan Opsera interactif n'a pas été lancé : l'outil exige une confirmation de paramètres que ce passage autonome ne peut pas collecter. Contrôle local : pas de jeton dans le dépôt.
- Pytest. GitHub Actions prévu pour les tests, le relevé et Pages.
