# Faisabilité des cotes

Mesures faites le 2 novembre 2026 depuis la VM (sortie Cloudflare `CMH`, États-Unis). Aucun contournement de géoblocage, de captcha ou de connexion. Une réponse refusée est notée comme refusée. Les chiffres ci-dessous sont ceux des réponses reçues, pas des cotes reconstituées.

La sonde peut être relancée depuis un runner GitHub Actions avec le workflow `Sonde`. Le premier passage Actions est à comparer à ce document : l'accès peut différer.

## Verdict

La référence sharp gratuite qui marche tout de suite est **Smarkets** (cotes d'échange, noms, prix, sans clé). **Pinnacle** publie des prix de ligue sans clé, mais refuse les noms de matchs (401). Sans les noms, ces prix ne sont pas utilisables. **Matchbook** répond, avec une liquidité souvent trop fine pour servir de référence.

Côté bookmakers agréés ANJ, trois flux ont renvoyé des cotes 1N2 le jour de la mesure :

| Source | Accès | Latence | Ce qu'on en tire |
| --- | --- | --- | --- |
| Unibet.fr | 200, jeton public déjà dans la page d'accueil | 0,3 s pour la page ligue, 0,4 s pour la Ligue 1 | 19 matchs de Ligue 1, tous en 1N2 |
| PMU (Kambi `pmusportsfr`) | 200 puis 410 si on enchaîne trop vite | 0,13 s | 10 matchs de Ligue 1, cotes horodatées |
| Netbet | 200, HTML de la page compétition | 0,9 s | 3 matchs seulement : la page ne contient pas tout le catalogue |

Winamax, Betclic, Olybet, Betsson et Genybet ont répondu 403 ou « accès refusé » depuis cette VM. ZEbet et l'ancienne adresse Parions Sport en ligne redirigent vers Unibet.fr. Rien de cela n'est contourné.

The Odds API répond 401 sans clé. Avec une clé gratuite (500 crédits par mois), elle peut ajouter Pinnacle. Sans clé, le relevé continue.

## Référence sharp

### Smarkets

`GET https://api.smarkets.com/v3/events/` puis, pour un marché, contrats et quotes. Réponse 200 en 0,15 à 0,22 s. En-tête `x-ratelimit-limit: 60` par minute.

Les prix sont des probabilités en dix-millièmes. Le milieu entre la meilleure demande et la meilleure offre est la probabilité retenue. Un côté manquant, ou un écart supérieur à 10 points, et le match est ignoré. On ne comble pas le trou.

Exemple reçu vers 01:16 UTC, Lorient–Brest, coup d'envoi 19:45 UTC :

| Issue | Meilleure cote back | Milieu |
| --- | --- | --- |
| Lorient | 2,50 | 39,53 % |
| Nul | 3,30 | 29,85 % |
| Brest | 3,15 | 31,03 % |

Après retrait de marge (méthode puissance) : 39,39 %, 29,71 %, 31,09 %.

### Pinnacle

`GET https://guest.api.arcadia.pinnacle.com/0.1/sports` : 200 en 0,04 s, football avec plusieurs centaines de matchs. Les marchés « straight » d'une ligue répondent aussi (Ligue 1 : 200, 433 ko, 0,04 s), en cotes américaines. `GET .../sports/29/matchups` : 401, « No authorization token provided ». Les prix sans noms de matchs ne sont pas appariés.

### Matchbook

`GET https://api.matchbook.com/edge/rest/events` : 200 en 0,15 à 0,32 s. Le premier exemple (Carabobo–Metropolitanos) n'avait que 4 USD au meilleur prix. Un runner sous 20 USD de liquidité est écarté.

### Betfair

L'endpoint de navigation du site a répondu 403. Pas d'appel supplémentaire.

## Books ANJ

### Unibet.fr

La page d'accueil (200, 175 ko, 0,9 s) contient un jeton anonyme `hsToken`, celui que le site envoie déjà à ses visiteurs. Il n'est pas écrit dans le dépôt ni dans les logs. Avec ce jeton :

- l'arbre des compétitions `/lvs-api/ept` répond 200 ;
- `/lvs-api/next/50/p{id}` pour la Ligue 1 répond 200 en 0,43 s, 34 ko, 19 matchs, chacun avec un marché `WIN_DRAW_WIN`.

Lorient–Brest : 2,30 / 3,00 / 3,00. Heure codée `2611021945`, lue comme 2 novembre 2026, 19:45 UTC.

Le flux Kambi `ub` (Unibet international) répond aussi, avec d'autres cotes (2,35 / 3,25 / 2,95, horodatées du 30 octobre). Ce n'est pas Unibet.fr. Il n'est pas utilisé.

### PMU

`https://eu-offering-api.kambicdn.com/offering/v2018/pmusportsfr/listView/...` a répondu 200 pour la Ligue 1 (20 ko, 0,14 s, 10 matchs), la Ligue 2 (7), la Premier League (11), la Liga (11), la Bundesliga (9) et la Ligue des champions (18). La Serie A en `football/italy/serie_a` a répondu 410 sur l'essai isolé : la ligue est demandée, et un 410 reste un échec visible.

Lorient–Brest chez PMU : 2,28 / 3,10 / 2,88, champ `changedDate` au 30 octobre 2026 08:20 UTC. La cote est quand même celle renvoyée par l'API le 2 novembre. Le relevé affiche l'ancienneté du dernier mouvement au-delà de 24 h. Il ne la remplace pas par une autre.

Après une rafale de requêtes, la même URL de Ligue 1 est passée de 200 à 410. Le client espace les ligues (0,8 s) et isole l'échec.

### Netbet

La page compétition contient les cotes dans le HTML servi. Les nombres répétés sont des variables (`odd:H`) : la cote lisible est `oddsDisplay`. Sur la page Ligue 1 du 2 novembre : 3 matchs, pas 19. Lorient–Brest : 2,37 / 3,05 / 2,85. La couverture partielle est indiquée dans l'état de la source.

### Les autres

| Site | Réponse |
| --- | --- |
| Winamax | 403 CloudFront |
| Betclic | 403 |
| Olybet | 403 Cloudflare |
| Betsson | 403, page « Geoloc redirection » |
| Genybet sport | 403 « Access denied » |
| Vbet | page d'accueil 200, pas d'API de cotes branchée |
| ZEbet, Parions Sport en ligne | redirection vers Unibet.fr |

Sofascore : 403. Pas de second essai déguisé.

## Exemple du 2 novembre, 01:16 UTC

Même match, même méthode (puissance), mêmes probabilités justes 39,39 / 29,71 / 30,89 %.

| Book | Cotes | Marge du book | EV domicile / nul / extérieur |
| --- | --- | --- | --- |
| Unibet | 2,30 / 3,00 / 3,00 | 10,1 % | −9,4 % / −10,9 % / −7,3 % |
| Netbet | 2,37 / 3,05 / 2,85 | 10,1 % | −6,6 % / −9,4 % / −12,0 % |
| PMU | 2,28 / 3,10 / 2,88 | 10,8 % | −10,2 % / −7,9 % / −11,0 % |

Aucune issue n'a d'espérance positive. Le meilleur panier (meilleure cote de chaque issue, books différents) laisse encore 7,8 % de marge. Ce n'est pas une surebet.

## Ce qui est retenu pour le relevé quotidien

1. Unibet.fr, PMU et Netbet comme books, chacun isolé si l'appel échoue.
2. Smarkets comme référence, prix chargés seulement pour les matchs déjà vus chez un book.
3. Matchbook seulement si la liquidité dépasse 20 USD sur les trois issues.
4. The Odds API, bookmaker Pinnacle, seulement si `ODDS_API_KEY` est présent.
5. Les sites en 403 sont sondés une fois et affichés comme non branchés.
6. Deux passages par jour (11:00 et 16:00 UTC), assez lents pour rester dans un usage raisonnable. Avec la clé Odds API, sept championnats deux fois par jour restent sous 500 crédits par mois.

La liste du téléphone peut donc être vide. C'est le comportement correct quand aucune cote française ne bat la référence.
