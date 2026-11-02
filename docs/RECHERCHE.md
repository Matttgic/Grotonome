# Pistes d'avantage

Chaque piste a été jugée sur des données, pas sur une intuition. Quand la donnée n'existe pas, la piste est écartée et c'est écrit.

La reproduction du contrôle historique est :

```bash
python scripts/recherche_historique.py --download --cache data/cache
```

Les CSV viennent de football-data.co.uk (saisons 2122 à 2526, championnats E0, F1, SP1, I1, D1). Ils ne sont pas dans le dépôt. Le script du 2 novembre 2026, sur un cache déjà téléchargé, a donné les chiffres ci-dessous.

## Protocole

- Décision : cotes d'ouverture seulement (Pinnacle `PSH/PSD/PSA`, Bet365 `B365H/D/A`).
- Mesure : clôture Pinnacle `PSCH/PSCD/PSCA`, deviguée par la même méthode, et résultat `FTR`.
- Un seul pari par match : l'issue dont l'EV d'ouverture est la plus haute, si elle passe le seuil.
- Mise de test : 1 unité. Le ROI n'est pas un Kelly.
- CLV : `cote prise × probabilité juste de clôture − 1`.
- Intervalle : normal à 95 % sur le profit unitaire. Il n'est pas calculé sous 2 paris.
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
| 5 % | 3 | −100 % | −6,3 % | +6,3 % | trois pertes |

L'entraînement, montré pour mémoire et non pour choisir, affichait un ROI de +10,6 % au seuil 0 % (n = 305) avec une CLV de +0,07 %. L'intervalle contient zéro. La CLV de test est négative à tous les seuils. L'EV annoncée à l'ouverture ne s'est pas retrouvée à la clôture.

Contrôle de bon sens : parier systématiquement le domicile chez Bet365 sur le test donne un ROI de −11,7 % et une CLV de −5,8 % (n = 2 650, intervalle entièrement négatif). Le calcul voit bien la marge.

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

Hypothèse : les fréquences passées domicile / nul / extérieur d'un championnat, calculées seulement avec les matchs déjà joués, battent Pinnacle quand elles s'en écartent d'au moins 5 points.

Test : 2 242 paris, ROI −17,8 %, CLV −10,5 %, intervalle −25,6 % à −10,1 %. L'EV « annoncée » par le modèle était de +90 %, ce qui mesure surtout son décalage avec le marché, pas un avantage.

Décision : aucun modèle de score dans le produit. La probabilité juste est celle du marché sharp, marge retirée.

## Ce qu'on ne sait pas

Il n'y a pas d'historique public des cotes Winamax, Betclic, Unibet.fr ou PMU aligné sur une clôture Pinnacle. Le suivi CLV et ROI de Grotonome commence donc à zéro, avec les paris que le relevé proposera vraiment. Tant que moins de deux paris sont réglés, l'intervalle de confiance n'est pas affiché.
