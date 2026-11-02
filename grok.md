# grok.md

## Règles

- Ne jamais inventer une cote, un résultat ou une performance. Une donnée manquante reste manquante.
- Ne jamais écrire un jeton, une clé ou un `hsToken` dans le code, les logs, les commits ou les pages.
- Pas de contournement de géoblocage, de captcha, de connexion ou de paiement.
- Les paris proposés ne visent que des books ANJ. Smarkets, Matchbook et Pinnacle sont des références, pas des endroits où envoyer jouer.
- Pas de pari automatique.
- Une source en échec est affichée. Elle ne bloque pas les autres.
- Backtest : la clôture et le résultat ne participent pas au choix du pari.
- Dépôt public : le journal des propositions est public.

## Commandes

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest
python3 -m grotonome sonde
python3 -m grotonome run --no-telegram
python3 scripts/recherche_historique.py --download --cache data/cache
```

## Erreurs à ne plus refaire

- Ne pas prendre le flux Kambi `ub` pour Unibet.fr. Les cotes diffèrent.
- Chez Netbet, ne pas lire `odd:` : les valeurs répétées sont des variables. Lire `oddsDisplay`.
- Ne pas committer le HTML Unibet : il contient le jeton anonyme.
- Un HTTP 410 Kambi peut suivre une rafale. Espacer les ligues. Ne pas enchaîner des dizaines d'essais.
- Smarkets annonce 60 requêtes par minute. Espacer d'environ une seconde les appels de prix.
- Ne pas apparier des prix Pinnacle tant que les noms de matchs sont refusés.
- Ne pas fusionner dans `main` si `python3 -m pytest` est rouge.
- Ne pas choisir le seuil d'EV sur la période de test.
- Les milieux Smarkets et Matchbook se normalisent. La puissance est pour les cotes décimales.
- Heure compacte Unibet : UTC. Lorient–Brest `2611021945` = 19:45Z, aligné sur PMU, Smarkets et Netbet.
- `OM` = Marseille, `OL` = Lyon, et seulement comme nom entier.
- Ne pas interpréter un `status:b` minifié chez Netbet.
