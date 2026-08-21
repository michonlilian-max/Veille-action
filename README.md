# Veille Actions — watchlist automatisée, essentiellement gratuite

Une petite application qui croise plusieurs signaux publics pour repérer
les actions à surveiller :

1. **Sentiment social** via l'API publique gratuite de StockTwits (substitut
   à X/Twitter, dont l'API payante est hors budget)
2. **Actualité financière** via le flux RSS gratuit de Google News
3. **Mouvements des initiés et des grands investisseurs** via SEC EDGAR
   (Form 4 = achats/ventes réels des dirigeants, code "P" uniquement ;
   13F-HR = positions institutionnelles)
4. **Prix et volume d'échange** via Yahoo Finance (`yfinance`) — distingue
   un vrai mouvement de marché d'un pic de bruit social
5. **(Optionnel, payant)** Sentiment X réel via Grok Live Search — la
   vraie donnée X que le point 1 ne peut pas se permettre gratuitement,
   activable si tu es prêt à payer l'API xAI (cf. section 7 de
   l'installation, avec estimation de coût)
6. **Autocritique quotidienne (backtest)** : chaque jour de bourse, après
   la clôture, le score calculé ce matin-là pour le top 30 est comparé au
   mouvement réel survenu ce jour-là — ça mesure, signal par signal,
   lequel a réellement précédé une hausse plutôt qu'une baisse (cf.
   section "Autocritique du score" plus bas)
7. **(Optionnel, gratuit)** Bot de trading **paper trading uniquement**
   (API Alpaca, argent fictif) : positions flexibles avec sorties
   bornées (revend automatiquement au-delà d'un seuil de gain ou de
   perte, garde le reste — jamais indéfiniment), email récapitulatif
   quotidien — vrai mécanisme d'exécution d'ordres, zéro risque
   financier (cf. section 8 de l'installation)
8. **Candidats S&P MidCap 400 à l'inclusion S&P 500** : une fois par
   semaine, repère parmi les ~400 sociétés du MidCap 400 celles qui
   ressemblent le plus à de bons candidats à une future entrée au S&P
   500 (proximité de capitalisation avec le plancher de l'indice +
   filtre de rentabilité) — l'entrée d'une société dans l'indice force
   les fonds indiciels à en acheter, un effet documenté (cf. section
   "Candidats MidCap 400" plus bas)

**Univers suivi : le S&P 500 (~500 sociétés), récupéré automatiquement à
chaque run** (cf. `scripts/fetch_sp500.py`) — plus une recomposition
manuelle de `config.py` à faire quand l'indice change. Si cette
récupération échoue, le pipeline retombe sur une liste de repli de 90
tickers curée à la main (`FALLBACK_WATCHLIST` dans `config.py`).

Le tout tourne sur GitHub Actions (planification automatique, un run par
nuit d'environ 3h à cette échelle) et s'affiche sur un dashboard statique
hébergé par GitHub Pages — gratuit dans sa configuration de base, à
l'exception du signal X optionnel (point 5).

⚠️ **Ce n'est pas un conseil en investissement.** C'est un indicateur d'attention
relative basé sur des signaux publics — à croiser avec ta propre analyse.

---

## Limites à connaître (important, lis avant de déployer)

- **StockTwits ≠ X/Twitter.** L'API X réelle est payante et hors de portée d'un
  budget serré. StockTwits est le meilleur substitut gratuit (communauté
  retail/trading comparable), mais ce n'est pas la même donnée. Son API
  publique n'a pas d'inscription développeur ouverte actuellement — elle
  fonctionne en accès non authentifié, mais **peut se fermer sans préavis**.
  Si `collect_stocktwits.py` casse, c'est le premier endroit à vérifier.
- **Le 13F a 45 jours de retard légal.** Les gros fonds ne sont pas obligés
  de publier leurs positions en temps réel — c'est une contrainte SEC, pas
  un bug du script.
- **Pas de "découverte" automatique de tickers en trending gratuitement.**
  Le script suit une liste fixe définie dans `config.py` (`WATCHLIST`).
  Ajoute/retire des tickers selon ce qui t'intéresse.
- **Google News RSS est bruité.** Certains articles retournés seront peu
  pertinents — c'est un compromis du gratuit vs une vraie API news payante.
- **Yahoo Finance (`yfinance`) est aussi un accès non officiel.** Comme
  StockTwits, ce n'est pas une API documentée avec garantie de service —
  c'est un accès gratuit à l'API interne de Yahoo Finance, largement
  utilisé par la communauté mais qui peut casser sans préavis. Si
  `collect_price.py` casse, c'est le deuxième endroit à vérifier après
  `collect_stocktwits.py`.
- **La liste S&P 500 dépend aussi d'une source externe non garantie**
  (`scripts/fetch_sp500.py`, jeu de données communautaire hébergé sur
  GitHub). Si elle devient indisponible ou change de format, le pipeline
  retombe automatiquement sur `FALLBACK_WATCHLIST` (90 tickers) plutôt que
  de planter — regarde les logs du run (`[fetch_sp500]` / `[config]`) pour
  savoir lequel des deux univers a réellement tourné.
- **StockTwits est maintenant le poste le plus long du run (~2h45 sur
  ~500 tickers)**, à cause de la limite de 200 requêtes/heure/IP de son
  API — impossible à contourner sans casser cette limite. Le run complet
  tient tout de même largement dans la fenêtre nocturne (voir section 3).

---

## Installation (10-15 minutes)

### 1. Mettre le projet sur ton GitHub

```bash
cd veille-actions
git init
git add .
git commit -m "Initial commit"
```

Crée un nouveau repo (public ou privé) sur github.com, puis :

```bash
git remote add origin https://github.com/TON_USER/veille-actions.git
git branch -M main
git push -u origin main
```

### 2. Personnaliser la config

Ouvre `config.py` et modifie :
- `SEC_USER_AGENT` → remplace par ton nom + ton email (la SEC exige un
  User-Agent identifiable, sinon elle bloque l'IP)
- `FALLBACK_WATCHLIST` → la liste de repli utilisée si la récupération
  automatique du S&P 500 échoue (`WATCHLIST` lui-même n'est pas à éditer :
  il est calculé dynamiquement, cf. `scripts/fetch_sp500.py`)

### 3. Activer GitHub Actions

Va dans l'onglet **Actions** de ton repo GitHub → active les workflows si
demandé. Le fichier `.github/workflows/veille.yml` est déjà configuré pour
tourner automatiquement **une fois par nuit** (03h00 UTC, mardi à samedi —
donc largement après la clôture des marchés US, pour capturer la clôture
de chaque jour de bourse de lundi à vendredi).

⏱️ **Sur l'univers S&P 500 (~500 tickers), un run complet prend environ
3 heures** (le principal poste étant StockTwits, contraint par sa limite
de 200 requêtes/heure/IP — voir "Limites à connaître"). Ça tient
largement dans la fenêtre nocturne avant la réouverture des marchés US et
dans la limite GitHub Actions de 6h par job — rien à faire de particulier,
juste ne pas s'étonner que le run ne soit pas terminé au bout de 10 minutes.

Pour un premier test immédiat sans attendre : onglet **Actions** →
sélectionne "Mise à jour de la veille" → **Run workflow**.

### 4. Activer GitHub Pages

Dans **Settings → Pages** de ton repo :
- Source : **GitHub Actions** (pas "Deploy from a branch")

Le dashboard sera ensuite accessible à `https://TON_USER.github.io/veille-actions/`
après le premier run réussi.

### 5. (Optionnel) Tester en local avant de déployer

```bash
pip install -r requirements.txt
python scripts/run_all.py
```

Puis ouvre `dashboard/index.html` dans un navigateur (ou lance
`python -m http.server` depuis la racine du projet et va sur
`http://localhost:8000/dashboard/`).

### 6. (Optionnel) Recevoir le rapport par email

À chaque run, `scripts/send_email.py` peut envoyer un email récapitulatif
(score + explication en clair de ce qui pousse chaque ticker) via ta propre
boîte mail — gratuit, pas de service tiers. Si ce n'est pas configuré, cette
étape est silencieusement ignorée et le reste du pipeline continue.

**a) Génère un "mot de passe d'application"** (jamais ton mot de passe
normal) sur ta boîte mail :
- **Yahoo Mail** : Compte → Sécurité → active la double authentification si
  besoin, puis "Générer un mot de passe d'application"
- **Gmail** : myaccount.google.com/apppasswords (nécessite la 2FA activée)

**b) Ajoute 5 secrets** dans **Settings → Secrets and variables → Actions →
New repository secret** de ton repo GitHub :

| Nom | Exemple |
|---|---|
| `SMTP_SERVER` | `smtp.mail.yahoo.com` (Gmail : `smtp.gmail.com`) |
| `SMTP_PORT` | `465` |
| `SMTP_USER` | ton adresse email complète |
| `SMTP_PASSWORD` | le mot de passe d'application généré à l'étape (a) |
| `EMAIL_TO` | adresse(s) destinataire(s), séparées par des virgules |

⚠️ Ces valeurs vont dans les **secrets GitHub**, jamais dans `config.py`
(qui est un fichier public du repo). Une fois les 5 secrets ajoutés, le
prochain run envoie automatiquement l'email — rien d'autre à faire.

### 7. (Optionnel, **PAYANT**) Sentiment X réel via Grok

Toutes les autres sources du projet sont gratuites. Celle-ci ne l'est
**pas** : elle utilise l'API xAI (Grok) et sa fonctionnalité "Live Search"
pour interroger X (Twitter) directement et analyser le sentiment réel des
posts — c'est la vraie donnée X que le reste du projet ne peut pas se
permettre (cf. la section "Limites à connaître" plus haut sur StockTwits).

**⚠️ Estimation de coût avant d'activer sur le cron automatique.** xAI
facture le modèle *et* Live Search par source récupérée (vérifie le tarif
à jour sur https://docs.x.ai — il peut avoir changé).

Le coût est **borné par `GROK_TOP_N` (30 par défaut), pas par la taille de
`WATCHLIST`** : Grok n'est interrogé que sur les 30 tickers les mieux
classés sur les signaux gratuits à chaque run (cf. `run_all.py`), jamais
sur les ~500 du S&P 500 en entier — sinon le coût exploserait avec la
taille de l'univers suivi. Avec les réglages par défaut
(`GROK_MAX_SEARCH_RESULTS = 8`, `GROK_TOP_N = 30`, cron d'un run/nuit,
mardi à samedi) :

```
5 runs/semaine × 30 tickers ciblés = 150 appels/semaine
150 × jusqu'à 8 sources ≈ jusqu'à 1 200 sources/semaine
```

Ça reste largement plus contenu que si Grok tournait sur tout l'univers
(qui donnerait ≈ jusqu'à 20 000 sources/semaine sur 500 tickers), mais
peut quand même chiffrer à plusieurs dizaines d'euros/mois selon le tarif
en vigueur. **Ne laisse pas tourner ça sur le cron sans avoir d'abord
testé manuellement** (`workflow_dispatch`) et vérifié ta conso réelle sur
https://console.x.ai. Pour réduire le coût : baisse
`GROK_MAX_SEARCH_RESULTS` et/ou `GROK_TOP_N` dans `config.py`, ou espace
davantage le cron.

**a) Crée une clé API** sur https://console.x.ai (nécessite une carte
bancaire).

**b) Ajoute 1 secret** dans **Settings → Secrets and variables → Actions**
de ton repo GitHub :

| Nom | Valeur |
|---|---|
| `GROK_API_KEY` | ta clé API xAI |

Si ce secret n'est pas configuré, ce signal contribue 0 au score et le
reste du pipeline continue normalement (comme l'email).

### 8. (Optionnel, gratuit) Bot de trading — PAPER TRADING UNIQUEMENT

⚠️ **Aucun argent réel n'est jamais engagé par ce bot.** Il utilise l'API
Alpaca en mode "paper trading" (portefeuille simulé, argent fictif) — le
code force ce mode en dur (`paper=True` dans `scripts/paper_trade.py`),
il n'existe aucun réglage dans ce projet pour basculer sur du trading
réel. C'est une décision délibérée : le score de ce projet est un
indicateur d'attention, pas un signal d'achat/vente validé (cf.
"Autocritique du score" ci-dessous) — y engager de l'argent réel sans
des mois de recul serait irresponsable.

**Positions flexibles, sorties bornées** — pas de "tout revendre chaque
soir" ni de "garder indéfiniment en espérant un rebond". Deux workflows
séparés :

**Entrée** (`.github/workflows/paper_trade.yml`, une fois par jour,
~9h35 ET) :
1. Récupère le score calculé par le run de nuit
2. Regarde les positions déjà ouvertes (reportées des jours précédents,
   pas encore sorties) — elles ne sont **jamais** revendues ici
3. N'achète que les tickers du top `PAPER_TRADING_TOP_N` (10 par défaut)
   qui ne sont pas déjà en portefeuille, dans la limite des places
   libres — capital réparti à parts égales entre les nouveaux achats

**Sortie** (`.github/workflows/check_paper_trade_exits.yml`, 5 fois par
jour pendant les heures de marché US) :
1. Pour chaque position ouverte, vend automatiquement dès que le gain
   latent dépasse `PAPER_TRADING_TAKE_PROFIT_PCT` (8% par défaut) **ou**
   que la perte latente dépasse `PAPER_TRADING_STOP_LOSS_PCT` (5% par
   défaut) — jamais gardée indéfiniment entre ces deux bornes, une
   position peut rester ouverte plusieurs jours sans problème
2. Au dernier passage de la journée, **envoie un email récapitulatif**
   (même mécanisme SMTP que le rapport principal, cf. section 6) :
   performance du compte du jour, nouvelles entrées, positions fermées
   (avec le gain/perte réel de chacune), positions encore ouvertes, et
   performance cumulée depuis le début

⚠️ **Pourquoi des bornes des deux côtés plutôt que "ne jamais vendre à
perte"** : garder indéfiniment un perdant en espérant un rebond ("l'effet
de disposition") est un biais comportemental documenté qui dégrade la
performance — le risque de perte devient illimité (l'action peut ne
jamais remonter), et le capital reste piégé au lieu d'être redéployé sur
de meilleurs candidats. Le stop-loss est volontairement plus serré que le
take-profit (5% vs 8%) : couper vite les pertes, laisser courir les
gains.

**a) Crée un compte** sur https://alpaca.markets (gratuit) et génère des
clés API en mode **Paper Trading** (pas "Live") depuis le tableau de bord.

**b) Ajoute 2 secrets** dans **Settings → Secrets and variables → Actions**
de ton repo GitHub :

| Nom | Valeur |
|---|---|
| `ALPACA_API_KEY` | ta clé API **paper trading** Alpaca |
| `ALPACA_SECRET_KEY` | ton secret **paper trading** Alpaca |

Si ces secrets ne sont pas configurés, le bot est ignoré (les deux
workflows) et le reste du pipeline continue normalement (même logique
que l'email et Grok). L'email récapitulatif réutilise en plus les 5
secrets SMTP de la section 6 — si l'email principal fonctionne déjà,
celui-ci fonctionne automatiquement aussi.

**But réel de cette fonctionnalité** : simuler, avec un vrai mécanisme
d'exécution d'ordres, ce qu'un bot ferait avec le score — pour voir dans
la durée si la stratégie aurait été rentable, sans rien risquer. Ce n'est
qu'une étape parmi d'autres avant d'envisager du réel un jour, pas une
recommandation d'y aller.

### 9. Candidats S&P MidCap 400 à l'inclusion S&P 500

Fonctionnalité gratuite, activée par défaut (pas de secret à configurer).
Tourne une fois par semaine (`.github/workflows/midcap_candidates.yml`,
dimanche 08h00 UTC) — le run est lourd (~900 appels individuels
`yfinance` pour récupérer capitalisation + bénéfices, plusieurs minutes),
pas la peine de le faire tourner chaque nuit vu que la composition de
l'indice ne change pas d'un jour à l'autre.

**Ce que fait `scripts/midcap_candidates.py`** :
1. Récupère la capitalisation boursière actuelle du S&P 500 **et** du
   S&P MidCap 400 (`scripts/fetch_midcap400.py` — scrape la page
   Wikipédia "List of S&P 400 companies", parsing défensif ; pas de CSV
   communautaire actif équivalent à celui du S&P 500 trouvé)
2. Calcule le "plancher" S&P 500 : moyenne des `SP500_FLOOR_SAMPLE_SIZE`
   (20 par défaut) plus petites capitalisations actuelles de l'indice
3. Exclut les candidats MidCap 400 dont le bénéfice par action (12 mois
   glissants) n'est pas positif — pas éligibles, peu importe leur taille
4. Score les candidats restants par proximité de capitalisation avec le
   plancher (dominant) + signaux d'attention déjà utilisés ailleurs dans
   le pipeline (news récentes, achats d'initiés, volume anormal)
5. Écrit le top `MIDCAP_TOP_N` (20 par défaut) dans
   `data/midcap_candidates.json`, affiché sur le dashboard
6. **Envoie un email récapitulatif** (même mécanisme SMTP que le rapport
   principal, cf. section 6 — réutilise automatiquement les 5 secrets
   déjà configurés, rien à ajouter) avec le plancher S&P 500 du moment et
   le détail de chaque candidat du top 20

⚠️ **Ce que ça n'est pas** : une prédiction fiable. L'inclusion au S&P
500 est décidée par un comité (S&P Dow Jones Indices) qui regarde aussi
l'équilibre sectoriel et la liquidité, pas seulement la capitalisation —
et l'annonce officielle n'arrive en général que quelques jours avant
l'effet réel. Le filtre de rentabilité (BPA 12 mois glissants) est une
approximation du vrai critère S&P (bénéfice GAAP positif sur les 4
derniers trimestres ET le dernier trimestre), plus lourd à calculer
précisément pour ~400 sociétés. C'est un candidat plausible à surveiller,
pas une certitude.

---

## Structure du projet

```
veille-actions/
├── config.py                    # univers suivi, pondérations du score, réglages
├── requirements.txt
├── scripts/
│   ├── fetch_sp500.py           # récupère la composition actuelle du S&P 500 (gratuit)
│   ├── collect_edgar.py         # Form 4 (achat/vente réel) + 13F via SEC EDGAR (gratuit)
│   ├── collect_news.py          # Google News RSS (gratuit)
│   ├── collect_price.py         # prix + volume via Yahoo Finance (gratuit)
│   ├── collect_stocktwits.py    # sentiment social (gratuit)
│   ├── collect_grok_sentiment.py # sentiment X réel via Grok Live Search (PAYANT, optionnel, ciblé sur GROK_TOP_N tickers)
│   ├── send_email.py            # rapport par email (SMTP, optionnel)
│   ├── scoring.py               # combine les signaux en un score composite
│   ├── history_utils.py         # utilitaire partagé : retrouver le score calculé ce matin
│   ├── backtest.py              # autocritique quotidienne : score du matin vs mouvement réel du jour
│   ├── paper_trade.py           # bot de trading, ENTRÉE — PAPER TRADING UNIQUEMENT (API Alpaca, optionnel)
│   ├── check_paper_trade_exits.py # bot de trading, SORTIE (take-profit/stop-loss) + email récap
│   ├── fetch_midcap400.py       # récupère la composition actuelle du S&P MidCap 400 (gratuit)
│   ├── collect_market_cap.py    # capitalisation boursière + BPA par ticker (yfinance, gratuit)
│   ├── midcap_candidates.py     # candidats MidCap 400 à l'inclusion S&P 500 (hebdomadaire)
│   └── run_all.py               # orchestrateur, point d'entrée
├── dashboard/
│   └── index.html               # dashboard statique (filtre par ticker + panneaux backtest, paper trading, MidCap 400)
├── data/
│   ├── output.json              # dernier résultat (lu par le dashboard)
│   ├── history/                 # archive des runs précédents (purgée après HISTORY_RETENTION_DAYS)
│   ├── backtest/                # journal quotidien du backtest (purgé après BACKTEST_RETENTION_DAYS)
│   ├── backtest_summary.json    # résumé par signal, une fois MIN_BACKTEST_SAMPLES atteint
│   ├── paper_trades/            # journal quotidien du bot paper trading (purgé après PAPER_TRADING_RETENTION_DAYS)
│   ├── paper_trades_summary.json # équité + performance actuelles du portefeuille simulé
│   └── midcap_candidates.json   # top candidats MidCap 400 de la semaine
└── .github/workflows/
    ├── veille.yml                     # collecte + score, planification + déploiement automatiques
    ├── backtest.yml                   # autocritique quotidienne après clôture des marchés
    ├── paper_trade.yml                # bot de trading : entrée, une fois par jour à l'ouverture
    ├── check_paper_trade_exits.yml    # bot de trading : sorties, 5x/jour + email récap au dernier passage
    └── midcap_candidates.yml          # candidats MidCap 400, une fois par semaine
```

## Comment le score est calculé

Chaque signal est normalisé sur 100 (relatif au max de la watchlist du jour),
puis combiné selon les poids définis dans `config.py` (`WEIGHTS`) :

- 25% sentiment X réel (Grok Live Search, **payant**, 0 si `GROK_API_KEY`
  non configuré, et 0 aussi pour tout ticker hors du top `GROK_TOP_N` sur
  les signaux gratuits — cf. section 7 de l'installation)
- 20% volume d'échange anormal + amplitude de variation du prix (Yahoo
  Finance, via `yfinance`) — distingue un vrai mouvement de marché d'un pic
  de bruit social sans rien derrière
- 15% sentiment social (ratio bullish/bearish StockTwits, pondéré par le volume)
- 15% volume de news récentes
- 15% vrais achats d'initiés en marché ouvert (Form 4, code de transaction
  "P" — les ventes et le bruit comme les attributions ou exercices
  d'options ne comptent plus, cf. `scripts/collect_edgar.py`)
- 10% présence dans un 13F récent

Ajuste ces poids librement selon ce que tu veux privilégier (ils doivent
sommer à 1.0). Si tu n'actives pas Grok (section 7), ses 25% ne rapportent
jamais rien — pense à redistribuer ce poids vers les autres signaux dans
`config.py` si tu ne comptes pas l'activer.

## Autocritique du score (backtest)

Le score ci-dessus est conçu comme un indicateur d'**attention** (ce ticker
bouge/fait parler de lui plus que d'habitude), pas un signal directionnel
achat/vente — c'est documenté depuis le début. Mais certains des 6 signaux
sont plausiblement directionnels par construction (un achat d'initié en
marché ouvert, `insider_buying`, est un vrai pari haussier ; le sentiment
X/social est nominalement directionnel), et d'autres non (`volume_spike`
et `news_volume` captent de l'attention dans n'importe quel sens — une
mauvaise nouvelle fait aussi exploser le volume).

`.github/workflows/backtest.yml` tourne chaque jour de bourse après la
clôture des marchés US (21h30 UTC) et exécute `scripts/backtest.py` :
- retrouve le score calculé **ce matin-là** (`data/history/`) pour le top
  `GROK_TOP_N` (30 par défaut)
- récupère le mouvement **réel** survenu ce jour-là pour ces tickers
  (Yahoo Finance), plus un taux de base sur toute la watchlist (pour
  savoir si le top 30 a fait mieux que le marché ce jour-là, pas juste
  "combien ont monté" dans l'absolu)
- journalise ça dans `data/backtest/` (un fichier par jour, conservé
  `BACKTEST_RETENTION_DAYS` jours, 180 par défaut)

Une fois `MIN_BACKTEST_SAMPLES` observations accumulées (300 par défaut,
soit ~10 jours de bourse — en dessous, une corrélation observée n'est que
du bruit de marché), un résumé est calculé par signal et écrit dans
`data/backtest_summary.json` :
- **corrélation** entre la valeur du signal et le mouvement réel signé du
  lendemain
- **taux de réussite directionnel** : parmi les tickers où ce signal
  était au-dessus de la médiane du jour, quelle proportion a réellement
  monté le lendemain — comparé au même taux quand le signal était en
  dessous, et au taux de base du marché ce jour-là

Ce résumé s'affiche automatiquement sur le dashboard (`dashboard/index.html`)
une fois qu'il existe.

**⚠️ Ce que ce backtest NE fait PAS** : il ne modifie jamais `WEIGHTS` dans
`config.py` tout seul. C'est un rapport de mesure, pas un pilote
automatique — même avec des mois de données, une corrélation historique
sur un échantillon de marché n'est pas une garantie que la relation
persiste, et un système qui réajuste ses propres poids sans supervision
humaine sur un signal aussi bruité est un bon moyen de sur-ajuster du
bruit statistique en le prenant pour un vrai signal. Si l'analyse
accumulée te convainc qu'un signal mérite plus (ou moins) de poids,
change `WEIGHTS` toi-même dans `config.py` en connaissance de cause.

## Prochaines améliorations possibles

- Alertes Telegram en plus de l'email (gratuit avec un webhook)
- N'envoyer l'email que si un ticker dépasse un seuil de score, plutôt que
  la watchlist complète à chaque run
- Ajouter Reddit (r/wallstreetbets, r/stocks) comme 2e source de sentiment
  social gratuite, en complément de StockTwits
- Short interest FINRA (gratuit, officiel, bi-mensuel) comme signal
  institutionnel supplémentaire
- Form 8-K (événements matériels) — l'infra CIK est déjà en place dans
  `collect_edgar.py`, il suffirait d'ajouter un type de formulaire
- Pondération temporelle (un Form 4 vieux de 29 jours pèse aujourd'hui
  pareil qu'un d'hier)
- Rendre le backtest actionnable sans casser la rigueur statistique : par
  exemple un rapport mensuel qui propose un `WEIGHTS` recalculé à partir
  des corrélations accumulées (toujours à valider et appliquer soi-même,
  cf. "Autocritique du score" plus haut — jamais automatique)
