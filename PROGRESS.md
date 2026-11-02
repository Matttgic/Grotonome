# PROGRESS

## Fait

- Mesure des sources le 2 novembre 2026 depuis la VM, sans contournement. Détail dans `docs/FAISABILITE.md`.
- Unibet.fr, PMU et Netbet (page partielle) renvoient des 1N2. Smarkets et Pinnacle servent de référence sharp. Winamax, Betclic, Olybet, Betsson, Genybet : accès refusé. Unibet.fr est instable (200 puis 403).
- Sonde GitHub Actions `41373331498` : PMU 78 matchs, Netbet 30, Smarkets 215, Matchbook 13, Unibet 403. Pinnacle a répondu ; les noms et le moneyline ont été branchés ensuite.
- Contrôle historique Bet365 contre Pinnacle, ouverture puis clôture, découpage au 1er juillet 2024. CLV de test négative. Détail dans `docs/RECHERCHE.md`.
- Moteur : retrait de marge, EV, quart de Kelly plafonné, appariement, pipeline qui isole une source en panne, journal, CLV, ROI, intervalle à partir de 2 valeurs.
- 33 tests au premier jet, puis 55 après la revue (PR #5), puis la deuxième passe. Commande : `python3 -m pytest`.
- Page mobile `site/`, workflows Tests, Quotidien, Sonde. Mode dégradé sans secrets.

## En cours

- La veille continue (workflow `Veille`) : boucle de 5 h, un relevé toutes les 6 minutes, cron de reprise toutes les 30 minutes. L'intervalle réel se lit dans les logs `RYTHME`.

## Prochaine étape

- Lire deux ou trois écarts `RYTHME` sur le premier job Actions. Pages reste hors sujet.

## Décisions

- Milieux d'échange (Smarkets, Matchbook) : normalisation. Sur (0,50 ; 0,29 ; 0,29), somme 1,08, la puissance met le favori à 47,36 % et la normalisation à 46,30 % (1,06 point). Ce n'est pas une marge de book. La puissance reste pour les cotes décimales, dont Pinnacle. Désaccord de plus de 8 points : pari écarté.
- Liquidité : Smarkets refuse en dessous de 10 000 (1 de devise, unité API × 10 000) ou si la quantité manque. Un plancher à 20 aurait écarté Portland–Houston, dont l'offre extérieure était à 22 027. Matchbook reste à 20 USD.
- Heure compacte Unibet : UTC. `2611021945` = 19:45Z, identique à PMU, Smarkets et Netbet 20:45+01 pour Lorient–Brest. L'heure de Paris donnerait 18:45Z, qui ne colle pas.
- `OM` = Marseille, `OL` = Lyon, seulement comme nom entier. `OL` ne matche pas Lens.
- Statut suspendu : Unibet (statut ou drapeau) et Netbet (mot « suspend » dans le bloc) retirent le 1N2. Un `status:b` minifié n'est pas interprété.
- Règlement CSV : date UTC, veille UTC et date de Paris. On ne règle que s'il n'y a pas deux résultats différents.
- Unibet et Parions Sport (FDJ) sont une seule source. Des cotes identiques sont normales. Nom affiché : « Unibet / Parions Sport ».
- Betclic.fr est en 403 CloudFront (POP CMH, page Betclic, pas un captcha), depuis la VM et depuis GitHub Actions. Les hôtes `apip.begmedia.com` et `offering.begmedia.com` répondent 404 sur les chemins essayés. Les cotes utilisées viennent de la page publique SportyTrader, horloge calée sur un coup d'envoi UTC déjà connu (Lorient–Brest : 14:45 affiché = 19:45Z, écart +5 h). Sans calage, aucune cote Betclic n'est émise. The Odds API a une clé `betclic_fr`, inutilisée faute de `ODDS_API_KEY`.
- Aucune piste française n'est déclarée rentable. L'historique horaire est là pour le mesurer plus tard.
- Books proposés : Unibet.fr, PMU, Netbet. Pas le flux Kambi `ub`, qui n'est pas Unibet.fr.
- Pas de modèle de score, pas de totaux, pas de boosts inventés, pas de chasse aux lignes mortes.
- Toute EV strictement positive est listée, avec l'avertissement historique. Aucun seuil « gagnant » n'est retenu.
- Mise : quart de Kelly, plafond 1,5 %. ROI de suivi à mise unitaire.
- Veille : un relevé toutes les 6 minutes dans un job d'au plus 5 h (les crons GitHub seuls sont trop irréguliers). Un cron toutes les 30 minutes reprend si la boucle meurt. Concurrence : un seul job, le suivant attend. Le récapitulatif Telegram part au premier passage après 8 h, heure de Paris, une fois par jour. L'alerte immédiate ne se répète que si la cote monte d'au moins 0,05 et d'au moins 3 %.
- Recul : après un 403 ou un 429, la source attend 15, 30, 60 puis 120 minutes. Les autres continuent. Pas de contournement.
- Clôture sharp : seulement dans les 15 minutes avant le coup d'envoi. Un relevé plus ancien ne compte pas comme CLV.
- Historique : `data/cotes.jsonl` ne reçoit que les cotes qui bougent d'au moins 0,01 (probabilités 0,005). L'état courant est `data/veille.json`. Les commits de données n'ont lieu qu'en cas d'alerte ou toutes les 30 minutes, et ils ne relancent pas les tests.
- Plus de deux photos par jour. Le workflow Quotidien reste un relevé manuel.
- Pas de clé Pinnacle à créer : la liste publique des matchs suffit. The Odds API reste facultative.

## Skills et outils externes

- Aucun skill externe installé : rien de vérifié n'apportait plus que le code déjà là, et un dépôt non lu ne rentre pas. Skill local ajouté : `skills/grotonome/SKILL.md` (règles de relevé pour les sessions suivantes).
- Délégations : aucune. Les décisions (devig, liquidité, heure, alias, statut, règlement) touchent les mêmes fonctions ; un sous-agent aurait refait les mêmes requêtes HTTP.
- Lecture des sites et API publiques par HTTP depuis la VM (pas de proxy, pas de Bright Data : un proxy aurait contourné le géoblocage, ce qui est exclu).
- football-data.co.uk pour l'historique, non versionné.
- Le scan Opsera interactif n'a pas été lancé : l'outil exige une confirmation de paramètres que ce passage autonome ne peut pas collecter. Contrôle local : pas de jeton dans le dépôt.
- Pytest. GitHub Actions prévu pour les tests, le relevé et Pages.
