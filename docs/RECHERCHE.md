# Pistes d'avantage

Chaque piste a été jugée sur des données, pas sur une intuition. Quand la donnée n'existe pas, la piste est écartée et c'est écrit.

La reproduction du contrôle historique est :

```bash
python scripts/recherche_historique.py --download --cache data/cache
```

Les CSV viennent de football-data.co.uk (saisons 2122 à 2526, championnats E0, F1, SP1, I1, D1). Ils ne sont pas dans le dépôt. Le script du 2 novembre 2026, sur un cache déjà téléchargé, a donné les chiffres ci-dessous.

## Protocole

- Décision : cotes d'ouverture seulement (Pinnacle `PSH/PSD/PSA`, Bet365 `B365H/D/A`). Un match sans clôture reste dans le ROI ; sa CLV est absente.
- Mesure : clôture Pinnacle `PSCH/PSCD/PSCA`, deviguée par la même méthode, et résultat `FTR`. La clôture ne sert pas à choisir le pari.
- Un seul pari par match : l'issue dont l'EV d'ouverture est la plus haute, si elle passe le seuil.
- Mise de test : 1 unité. Le ROI n'est pas un Kelly.
- CLV : `cote prise × probabilité juste de clôture − 1`.
- Intervalle : normal à 95 % sur le profit unitaire. Il n'est pas calculé sous 2 paris, ni quand tous les profits sont identiques (la variance nulle ne doit pas dessiner un intervalle de largeur zéro).
- Découpage fixé avant de lire le test : entraînement jusqu'au 30 juin 2024 (5 402 matchs, du 6 août 2021 au 2 juin 2024), test à partir du 1er juillet 2024 (2 654 matchs, du 15 août 2024 au 15 janvier 2026). Les seuils 0 %, 2 % et 5 % sont fixés d'avance. Le seuil qui « marche » n'est pas choisi sur le test.
- 8 056 matchs ont une ouverture Pinnacle et un résultat. Bet365 n'est pas un book ANJ. C'est le seul historique public soft contre sharp trouvé sans clé. L'extrapolation aux books français n'est pas faite.

La méthode puissance a un score de Brier légèrement meilleur que la méthode proportionnelle sur l'entraînement (0,5768 contre 0,5769, n = 5 402). L'écart est minuscule. La puissance est quand même la méthode du produit, parce que le choix se fait sur l'entraînement. Le test va dans le même sens (0,5725 contre 0,5728) et n'a pas servi à choisir.

## 1. Value contre la cote sharp d'ouverture

Hypothèse : si Bet365 offre, à l'ouverture, une cote au-dessus de la probabilité Pinnacle deviguée, le pari a une CLV positive et un ROI positif plus tard.

Résultat sur le test :

| Seuil d'EV | Paris | ROI | CLV moyenne | EV annoncée | IC 95 % du profit unitaire |
| --- | --- | --- | --- | --- | --- |
| 0 % | 128 | +1,23 % | −0,58 % | +1,28 % | −27,9 % à +30,4 % |
| 2 % | 27 | −17,5 % | −4,0 % | +3,6 % | −77 % à +42 % |
| 5 % | 3 | −100 % | −6,3 % | +6,3 % | non calculé (trois pertes, variance nulle) |

L'entraînement, montré pour mémoire et non pour choisir, affichait un ROI de +10,6 % au seuil 0 % (n = 305) avec une CLV de +0,07 %. L'intervalle contient zéro. La CLV de test est négative à tous les seuils. L'EV annoncée à l'ouverture ne s'est pas retrouvée à la clôture.

Contrôle de bon sens : parier systématiquement le domicile chez Bet365 sur le test donne un ROI de −11,8 % et une CLV de −5,8 % (n = 2 654, CLV sur les 2 650 matchs qui ont une clôture, intervalle −16,3 % à −7,3 %, entièrement négatif). Le calcul voit bien la marge.

Décision : le produit affiche les écarts du jour, il ne les présente pas comme une stratégie gagnante. Aucun seuil historique n'est assez solide pour filtrer « ce qui gagne ». La liste retient toute EV strictement positive, plafonne la mise, et répète ce résultat.

## 2. Cotes obsolètes après un mouvement

Hypothèse : le book soft est en retard sur Pinnacle, donc une cote d'ouverture trop haute bat la clôture.

La CLV du test est négative. En moyenne, quand Bet365 était au-dessus de Pinnacle à l'ouverture, la clôture Pinnacle n'a pas confirmé l'écart. La piste « ligne morte » n'est pas soutenue par cet historique.

Sur le relevé du 2 novembre, la cote PMU de Lorient–Brest portait un dernier mouvement au 30 octobre. Elle n'était pas plus haute que Unibet ou Netbet. Un vieux mouvement n'est donc pas, à lui seul, une value. Le produit le signale s'il a plus de 24 h. Il ne l'invente pas en cote fraîche.

Décision : pas de chasse aux lignes mortes. Avertissement d'ancienneté seulement.

## 3. Marchés secondaires

Hypothèse : les totaux (plus ou moins de 2,5) sont moins bien tenus que le 1N2.

Sur le test, au seuil 2 %, avec ouverture Pinnacle contre Bet365 et clôture Pinnacle : 4 paris, ROI −100 %, CLV +10 % sur un échantillon trop petit pour conclure. L'intervalle n'a aucun sens à n = 4 avec quatre pertes.

Décision : le relevé ne propose pas les totaux. Le 1N2 est le seul marché dont l'appariement des noms est vérifié.

## 4. Boosts et promos

Aucune source gratuite et structurée n'a renvoyé un boost chiffré rattaché à un match. Les pages promo existent, elles ne sont pas un flux de cotes.

Décision : hors produit. Un boost non lu n'est pas compté comme de l'EV.

## 5. Surebet entre books français

Hypothèse : le meilleur prix de chaque issue, pris chez des books ANJ différents, somme parfois à moins de 1.

Le 2 novembre, Lorient–Brest : meilleure cote 2,37 (Netbet), 3,10 (PMU), 3,00 (Unibet). Somme des inverses = 1,078. Marge restante 7,8 %. Pas de surebet.

Le détecteur est dans le relevé (`combined_overround`). Il n'affiche une surebet que si la marge calculée est négative. L'historique football-data n'a pas été utilisé pour compter des surebets anglaises : ce ne sont pas les books demandés.

Décision : afficher la marge de shopping quand deux books couvrent le même match. Ne pas annoncer de fréquence historique.

## 6. Modèle maison

Hypothèse : les fréquences passées domicile / nul / extérieur d'un championnat, calculées seulement avec les matchs des jours déjà terminés, battent Pinnacle quand elles s'en écartent d'au moins 5 points. Les autres matchs du même jour ne comptent pas encore : leur résultat n'est pas connu au coup d'envoi.

Test : 2 247 paris, ROI −17,9 %, CLV −10,5 %, intervalle −25,6 % à −10,2 %. L'EV « annoncée » par le modèle était de +90 %, ce qui mesure surtout son décalage avec le marché, pas un avantage.

Décision : aucun modèle de score dans le produit. La probabilité juste est celle du marché sharp, marge retirée.

## 7. Deuxième passe, 2 novembre 2026 au soir

Livres français supplémentaires. ZEbet et Parions Sport en ligne redirigent vers Unibet.fr (réponse finale 200 sur `www.unibet.fr`). Les compter à part doublerait les mêmes cotes. Betclic, Olybet, Genybet et Betsson répondent 403. Feelingbet ne résout pas. Winamax, en revanche, publie son offre dans la page `https://www.winamax.fr/paris-sportifs` (`PRELOADED_STATE`) : 76 matchs sur la page d'accueil au moment de la lecture, dont des avant-match football avec un marché « Résultat ». Exemple lu : Portland Timbers – Houston Dynamo, 1,64 / 3,70 / 3,75, statut `PREMATCH`, coup d'envoi 02:45 UTC. C'est branché. Ce n'est pas une preuve d'avantage.

Milieux d'échange. Sur (0,50 ; 0,29 ; 0,29), somme 1,08, la puissance donne 47,36 % au favori et la simple normalisation 46,30 %, soit 1,06 point. Cet écart n'est pas une marge de bookmaker, c'est le carnet. Les milieux sont donc normalisés. La puissance reste réservée aux cotes décimales (Pinnacle, et un book s'il sert de référence).

Liquidité. Smarkets : quantité minimale 10 000, soit 1 de devise si l'unité publiée est le montant × 10 000. En dessous, ou si la quantité manque, le carnet ne fixe pas la probabilité. Un essai à 20 (200 000) a été écarté : sur Portland–Houston, la meilleure offre extérieure valait 22 027 et le match entier disparaissait. Matchbook reste à 20 USD, et 11 matchs passaient encore ce soir-là.

Heure Unibet. Le code `2611021945` de Lorient–Brest, lu en UTC, vaut 19:45Z, qui est l'heure PMU, Smarkets et Netbet (20:45+01). Lu en heure de Paris, il vaudrait 18:45Z et ne collerait à aucune de ces sources. On garde UTC.

Alias. `OM` et `OL` désignent Marseille et Lyon, uniquement quand c'est le nom entier. `OL` ne matche pas Lens.

Suspendu. Une issue Unibet dont le statut ou le drapeau dit suspendu, fermé ou non coté retire tout le 1N2. Chez Netbet, le mot « suspend » dans le bloc de l'issue fait de même. Un code minifié (`status:b`) n'est pas interprété : ce serait deviner.

Règlement. Un coup d'envoi après minuit UTC peut être daté la veille dans le CSV. On regarde la date UTC, la veille UTC et la date de Paris. On règle seulement si ces dates ne se contredisent pas.

CLV française. Chaque relevé ajoute `data/cotes.jsonl` (cote du book et référence sharp, avec l'heure). La CLV n'est calculée que lorsqu'une cote française a une référence au moment du relevé et une référence plus tardive avant le coup d'envoi. L'issue mesurée est celle qui était la meilleure à l'ouverture, pas celle qui le devient à la clôture. Au moment d'écrire ces lignes, il n'y a pas encore deux instants : la moyenne n'existe pas, et ce n'est pas affiché comme un zéro.

Marchés secondaires et boosts. Le référentiel promo Unibet (`Referentiel_offres_promos_markets_Unibet.json`) liste des types de marchés, pas des cotes boostées. Les totaux UK restent à 4 paris. Rien n'est ajouté à la liste de paris.

Relevé lancé juste après, vers 02:20 UTC, avec le plancher Smarkets encore à 20 : Winamax 22 matchs avant-match, PMU 55 (Premier League et Serie A en HTTP 410), Netbet 34, Unibet.fr 403, Pinnacle 403, Smarkets listé (214) mais aucun prix retenu, Matchbook 11. 122 lignes dans `data/cotes.jsonl` (books et Matchbook). Aucune espérance positive. CLV française : n = 0. Ce n'est pas un ROI de zéro, c'est une mesure qui n'existe pas encore. Le plancher Smarkets a été baissé à 1 ensuite, pour le passage suivant.

Décision : pas de stratégie déclarée rentable. Winamax entre dans le relevé. L'historique horaire commence pour pouvoir, plus tard, dire si les livres français ont une CLV.

## Ce qu'on ne sait pas

Il n'y a pas d'historique public des cotes Winamax, Betclic, Unibet.fr ou PMU aligné sur une clôture Pinnacle. Le suivi CLV et ROI de Grotonome commence donc à zéro, avec les paris que le relevé proposera vraiment. Tant que moins de deux paris sont réglés, l'intervalle de confiance n'est pas affiché.
