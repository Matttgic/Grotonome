# Grotonome

Grotonome compare les cotes de bookmakers agréés ANJ à une probabilité estimée sur un marché sharp, puis affiche une liste courte sur téléphone. Il ne place aucun pari.

Le dépôt est public. Le journal des paris proposés l'est aussi. Aucune clé n'y est écrite.

Écrit de zéro, sans reprendre un autre dépôt de cotes.

## Ce que le téléphone reçoit

Deux fois par jour (11:00 et 16:00 UTC), un passage GitHub Actions interroge les sources, écrit `site/latest.json` et, si Telegram est configuré, envoie le même résumé.

Chaque ligne affiche la cote, le bookmaker, l'espérance, la mise conseillée (fraction de bankroll, et des euros si `BANKROLL_EUR` est défini) et l'heure limite, en heure de Paris.

Si aucune cote n'a d'espérance positive, le message le dit. Une cote manquante n'est pas remplacée.

## Lire la liste

Une fois GitHub Pages actif, ouvrir l'adresse du site (Settings → Pages, ou le lien affiché par le workflow). La page est prévue pour un écran de téléphone.

Avant le premier passage, la page indique qu'il n'y a pas encore de relevé.

Lancer un passage depuis le téléphone :

1. Ouvrir `https://github.com/Matttgic/Grotonome` dans Chrome.
2. Si l'onglet Actions n'apparaît pas, menu Chrome → Site pour ordinateur.
3. Actions → Quotidien → Run workflow → branche `main`.

## Tests

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest
```

`python3 -m pytest` est la commande unique des tests. Ils couvrent le retrait de marge, l'espérance, la mise, la CLV et des extraits de réponses réelles. Ils ne contactent aucun site.

Le contrôle historique, qui télécharge des CSV, est séparé :

```bash
python3 scripts/recherche_historique.py --download --cache data/cache
```

## Configuration depuis un téléphone Android

Rien de tout cela n'est obligatoire pour que le relevé tourne. Sans ces valeurs, Telegram est ignoré, la mise reste une fraction, et Pinnacle via The Odds API est absent. Le reste continue.

### Telegram

1. Installer Telegram.
2. Chercher `@BotFather`, envoyer `/newbot`, suivre les questions.
3. Copier le jeton. Ne pas le coller dans une note publique, ni dans la barre d'adresse.
4. Ouvrir la conversation du bot et envoyer un message.
5. Chercher `@userinfobot`, envoyer `/start`. L'`Id` affiché est l'identifiant de discussion à mettre dans GitHub.
6. Dans Chrome, ouvrir le dépôt, passer en site pour ordinateur.
7. Settings → Secrets and variables → Actions → New repository secret.
8. Nom `TELEGRAM_BOT_TOKEN`, valeur : le jeton.
9. Deuxième secret, nom `TELEGRAM_CHAT_ID`, valeur : l'identifiant.

### Bankroll

Settings → Secrets and variables → Actions → onglet Variables → New repository variable.

Nom `BANKROLL_EUR`, valeur un nombre, par exemple `200`. Ce n'est pas un secret, mais ça évite de l'écrire dans le code. Sans cette variable, la mise est seulement un pourcentage.

### The Odds API, pour ajouter Pinnacle

1. Ouvrir `https://the-odds-api.com` et créer un compte gratuit.
2. Copier la clé.
3. Secret GitHub `ODDS_API_KEY`.

Le palier gratuit est d'environ 500 crédits par mois. Deux passages par jour sur sept championnats restent en dessous. Si le quota est dépassé, cette source passe en échec et les autres continuent.

Pinnacle est déjà lu sans compte : les noms viennent de la liste publique, les prix des matchs appariés. Ne créez pas de compte Pinnacle pour ce dépôt.

### GitHub Pages

Settings → Pages → Build and deployment → Source : GitHub Actions.

Le workflow `Quotidien` publie le dossier `site`. S'il échoue au premier déploiement, c'est en général cette option qui manque. Le journal, lui, est quand même poussé sur `main` si le relevé a réussi.

## Sources et limites

Le détail des mesures est dans [docs/FAISABILITE.md](docs/FAISABILITE.md). Les pistes testées et écartées sont dans [docs/RECHERCHE.md](docs/RECHERCHE.md).

En bref, le 2 novembre 2026 : Unibet.fr, PMU et une page partielle Netbet répondent. Smarkets sert de référence. Winamax, Betclic, Olybet, Betsson et Genybet ont refusé la VM, sans contournement. Sur l'historique Bet365 contre Pinnacle (proxy, pas un book ANJ), la CLV hors échantillon est négative ou non significative. Grotonome le répète sur la page.

La probabilité juste est la cote sharp dont on a retiré la marge par la méthode puissance. L'espérance est `probabilité × cote − 1`. La mise est un quart de Kelly, plafonné à 1,5 % de la bankroll.

Le ROI suivi est celui d'une mise de 1. La CLV compare la cote prise à la probabilité juste du dernier relevé sharp avant le coup d'envoi. Moins de deux paris réglés : pas d'intervalle.
