# Faisabilité des cotes

Mesures faites le 2 novembre 2026 depuis la VM (sortie Cloudflare `CMH`, États-Unis). Aucun contournement de géoblocage, de captcha ou de connexion. Une réponse refusée est notée comme refusée. Les chiffres ci-dessous sont ceux des réponses reçues, pas des cotes reconstituées.

La sonde se relance depuis un runner GitHub Actions (workflow `Sonde`, à la main ou quand ce fichier de workflow change). Le résultat du premier passage Actions est ajouté en bas de ce document dès qu'il est lu.

## Betclic, 2 novembre au matin

Le site `www.betclic.fr` (accueil, football, robots.txt, sitemap) répond **403** depuis cette VM. L'en-tête `X-Amz-Cf-Pop: CMH68-P3` et `X-Cache: Error from cloudfront` montrent un blocage CloudFront, page HTML « Betclic - Error 403 Forbidden », pas un captcha. Le même 403 avait été vu sur un runner GitHub Actions. Un navigateur mobile normal (Chrome Android, `Accept-Language: fr-FR`) ne change pas le code. `m.betclic.fr` et `www.betclic.com` font de même. On n'a pas cherché à imiter une empreinte TLS ni à passer par un proxy : ce serait contourner le blocage.

`apip.begmedia.com` et `offering.begmedia.com` répondent, mais les chemins publics essayés (`/api/pub/v2` à `v4` `/sports`, `/web/offering/v5/sports`) renvoient **404** « Route not found » ou « Not found », pas des cotes. Sans le JavaScript du site, bloqué avec lui, le chemin courant n'est pas lisible. The Odds API documente un bookmaker `betclic_fr` (régions `eu` et `fr`) : il faut une clé, que ce dépôt n'a pas.

La page publique SportyTrader, elle, affiche le 1N2 Betclic. Le 2 novembre, Lorient–Brest y est coté **2,35 / 3,10 / 2,83**. L'heure affichée « 02 nov. - 14:45 » correspond à 19:45 UTC une fois calée sur le coup d'envoi déjà connu (écart +5 h depuis cette IP américaine). Sans ce calage, les cotes ne sont pas utilisées. C'est ce relais qui alimente la liste, pas une API Betclic.

## Fraîcheur du relais SportyTrader, 2 novembre 2026

Verdict : **retard médian non calculable**. L'échantillon est trop petit (0 suivi).

`data/cotes.jsonl` au commit `6eff1f0` compte 252 lignes, de `2026-11-02T02:20:15Z` à `2026-11-02T03:50:03Z`. Répartition : PMU 135, Netbet 69, Matchbook 26, Winamax 22. Aucune ligne Betclic, Pinnacle, Smarkets ou Unibet. Le script `python3 scripts/retard_betclic.py data/cotes.jsonl` trouve 3 mouvements sharp (tous Matchbook) et 1 mouvement PMU. Unibet : 0. Winamax : 0. Aucun de ces mouvements n'a de cote Betclic antérieure sur le même match, donc aucun délai. Suivis : 0. Censurés : 0. Médian sharp → Betclic : non calculable. Médian Unibet / Winamax / PMU → Betclic : non calculable. Le seuil pour publier un médian est 8 suivis sharp.

Pourquoi zéro ligne Betclic : le job de veille `41384155415` a démarré à 03:37 UTC, avant le commit `96cca3a` (03:52 UTC) qui lit SportyTrader. Ce job garde l'ancien code jusqu'à sa fin. Les relevés toutes les ~6 minutes de cette fenêtre ne peuvent pas mesurer le relais.

En-têtes lus à 03:59 UTC depuis cette VM (une page ligue, une page match, sans enchaîner) :

| Page | Code | Cache-Control | Age | Last-Modified | Cloudflare |
| --- | --- | --- | --- | --- | --- |
| `https://www.sportytrader.com/cotes/football/france/ligue-1-123/` | 200, 405 ko | `max-age=0, public, s-maxage=600` | absent | absent | `cf-cache-status: HIT` |
| `https://www.sportytrader.com/cotes/lorient-brest-8532705/` | 200, 1,6 Mo | `max-age=0, public, s-maxage=600` | absent | absent | `cf-cache-status: EXPIRED` |

`s-maxage=600` veut dire que le CDN peut servir la page pendant 10 minutes. Ce n'est pas le retard face à Betclic. La page ligue contient des heures ISO de coup d'envoi (`2026-11-02T19:45`), pas une heure de cotation. Aucun texte « mise à jour » ou `datetime`. Sur la page match, à 03:59 UTC, la pastille domicile Betclic est encore 2,35. Les deux autres issues n'ont pas été relues à cet instant.

Limite d'âge retenue en attendant la mesure : **2 points de probabilité juste**. Une cote Betclic identique à la précédente (écart inférieur à 0,01) sort de la liste et de l'alerte si le sharp a bougé d'au moins 0,02 depuis l'ancre posée au dernier changement de cette cote. Deux points, c'est quatre fois le seuil qui enregistre une probabilité (0,005). Chaque pari Betclic qui reste porte l'avertissement « cote relayée, à vérifier dans l'appli Betclic », dans la liste et dans l'alerte. Le script ci-dessus refait la mesure quand la veille aura accumulé des lignes Betclic.

## Unibet et Parions Sport

Parions Sport en ligne (FDJ) et Unibet servent la même offre. Des cotes identiques sont le fonctionnement normal, pas un doublon à arbitrer. Le relevé ne les interroge qu'une fois, sous le nom affiché « Unibet / Parions Sport ». ZEbet redirige aussi vers Unibet.fr.

## Winamax, relu le 2 novembre au soir

La page `https://www.winamax.fr/paris-sportifs` répond 200 (environ 370 ko) et contient `PRELOADED_STATE` : matchs, marché « Résultat », cotes. `wapi.winamax.fr` répond 200 avec « Invalid request » : ce n'est pas un flux de cotes sans le corps d'appel du site, et ce corps n'a pas été rejoué. Betclic, Olybet, Genybet et Betsson restent en 403. ZEbet et Parions Sport en ligne aboutissent sur Unibet.fr.

## Verdict

Deux références sharp marchent sans clé. **Smarkets** donne le carnet d'ordres. **Pinnacle** donne les noms des matchs (`/sports/29/matchups`, 200) et, match par match, un 1N2 en cotes américaines avec les rôles domicile, nul, extérieur. **Matchbook** répond, mais beaucoup de matchs n'ont pas assez de liquidité (seuil retenu : 20 USD).

Un premier passage GitHub Actions (run `41373331498`, 2 novembre 2026, 01:36 UTC, runner Ubuntu) a confirmé PMU, Netbet, Smarkets et Matchbook. Unibet.fr y a répondu 403, comme un second essai depuis la VM le même jour. Le détail est plus bas.

Côté bookmakers agréés ANJ, trois flux ont renvoyé des cotes 1N2 le jour de la mesure :

| Source | Accès | Latence | Ce qu'on en tire |
| --- | --- | --- | --- |
| Unibet.fr | 200, jeton public déjà dans la page d'accueil | 0,3 s pour la page ligue, 0,4 s pour la Ligue 1 | 19 matchs de Ligue 1, tous en 1N2 |
| PMU (Kambi `pmusportsfr`) | 200 puis 410 si on enchaîne trop vite | 0,13 s | 10 matchs de Ligue 1, cotes horodatées |
| Netbet | 200, HTML de la page compétition | 0,9 s | 3 matchs seulement : la page ne contient pas tout le catalogue |

Le soir du 2 novembre, Winamax répond 200 et ses cotes sont dans la page (voir plus haut). Betclic, Olybet, Betsson et Genybet restent en 403. ZEbet et Parions Sport en ligne redirigent vers Unibet.fr. Rien de cela n'est contourné.

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

Après retrait de marge (méthode puissance) : 39,39 %, 29,71 %, 30,89 %.

### Pinnacle

`GET https://guest.api.arcadia.pinnacle.com/0.1/sports` : 200 en 0,04 s. Avec l'identifiant du client Grotonome, `GET .../sports/29/matchups` répond 200 (liste de matchs nommés, environ 0,5 s). Un essai antérieur avec un autre user-agent avait reçu 401 : ce n'est pas un contournement, c'est l'en-tête que le programme envoie déjà.

Les prix d'un match : `GET .../matchups/{id}/markets/straight`, 200. Le moneyline période 0 porte `designation` home, draw, away et une cote américaine. Exemple lu : −353, 391, 635, soit 1,283, 4,91 et 7,35 en décimal. Le relevé ne télécharge ces prix que pour les matchs déjà vus chez un book français.

Le marché d'une ligue entière a répondu 200 une fois, puis 403. Il n'est pas utilisé.

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

Un appel plus tardif le même jour, toujours depuis la VM, a reçu un 403 DataDome (page captcha). Le premier relevé, lui, était bien un 200. Unibet.fr est donc joignable, mais pas stable depuis un centre de données. Le captcha n'est pas contourné : ce jour-là la source passe en échec, PMU, Netbet et Smarkets continuent, et l'échec est visible.

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

## Sonde GitHub Actions

Run [41373331498](https://github.com/Matttgic/Grotonome/actions/runs/41373331498), 25 s, succès. À ce moment-là le code ne lisait pas encore les noms Pinnacle : la ligne Pinnacle dit seulement que la réponse est arrivée.

| Source | Runner | VM, plus tôt le même jour |
| --- | --- | --- |
| Unibet.fr | échec, HTTP 403 | 200, puis 403 DataDome plus tard |
| PMU | ok, 78 matchs (Ligue 1 : 10, Ligue 2 : 7, Premier League : 11, Liga : 11, Serie A : 12, Bundesliga : 9, Ligue des champions : 18), 3,5 s | 200 sur plusieurs ligues, 410 si on insiste |
| Netbet | ok, 30 matchs sur 4 pages partielles, 4,8 s | 3 matchs sur la seule page Ligue 1 testée |
| Smarkets | ok, 215 matchs listés, 2,1 s | 200, carnet lu sur Lorient–Brest |
| Matchbook | ok, 13 matchs au-dessus du seuil de liquidité, 0,5 s | 200, liquidité souvent faible |
| Pinnacle | réponse reçue (le parseur de noms a été branché ensuite) | noms et moneyline lus ensuite, voir plus haut |
| The Odds API | inactive, pas de clé | 401 sans clé |
| Winamax, Betclic, Olybet, Betsson | 403 | 403 |
| Genybet | accès refusé | accès refusé |
| Vbet | page ouverte, pas de cote branchée | page ouverte |

L'accès diffère surtout pour Unibet.fr, instable, et pour la Serie A PMU, qui a répondu sur le runner (12 matchs) après un 410 depuis la VM.

## Ce qui est retenu pour le relevé quotidien

1. Unibet.fr, PMU et Netbet comme books, chacun isolé si l'appel échoue.
2. Smarkets et Pinnacle comme références. Les prix ne sont chargés que pour les matchs déjà vus chez un book. S'ils divergent de plus de 8 points sur une issue, le pari est écarté.
3. Matchbook seulement si la liquidité dépasse 20 USD sur les trois issues.
4. The Odds API, seulement si `ODDS_API_KEY` est présent. Ce n'est pas nécessaire pour avoir Pinnacle.
5. Les sites en 403 sont sondés une fois et affichés comme non branchés.
6. Deux passages par jour (11:00 et 16:00 UTC). Avec une clé Odds API, sept championnats deux fois par jour restent sous 500 crédits par mois. Sans cette clé, il n'y a pas de quota.

La liste du téléphone peut donc être vide. C'est le comportement correct quand aucune cote française ne bat la référence.
