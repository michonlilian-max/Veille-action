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

Le tout tourne sur GitHub Actions (planification automatique) et s'affiche
sur un dashboard statique hébergé par GitHub Pages — gratuit dans sa
configuration de base, à l'exception du signal X optionnel (point 5).

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
- `WATCHLIST` → la liste des tickers que tu veux suivre

### 3. Activer GitHub Actions

Va dans l'onglet **Actions** de ton repo GitHub → active les workflows si
demandé. Le fichier `.github/workflows/veille.yml` est déjà configuré pour
tourner automatiquement toutes les 4 heures en semaine.

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
à jour sur https://docs.x.ai — il peut avoir changé). Avec les réglages
par défaut (`GROK_MAX_SEARCH_RESULTS = 8` dans `config.py`, 16 tickers, et
le cron par défaut de 6 runs/jour en semaine) :

```
30 runs/semaine × 16 tickers = 480 appels/semaine
480 × jusqu'à 8 sources ≈ jusqu'à 3 840 sources/semaine
```

Ça peut vite chiffrer à plusieurs dizaines voire centaines d'euros/mois
selon le tarif en vigueur. **Ne laisse pas tourner ça sur le cron sans
avoir d'abord testé manuellement** (`workflow_dispatch`) et vérifié ta
conso réelle sur https://console.x.ai. Pour réduire le coût : baisse
`GROK_MAX_SEARCH_RESULTS`, réduis la taille de `WATCHLIST`, ou espace
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

---

## Structure du projet

```
veille-actions/
├── config.py                    # watchlist, pondérations du score, réglages
├── requirements.txt
├── scripts/
│   ├── collect_edgar.py         # Form 4 (achat/vente réel) + 13F via SEC EDGAR (gratuit)
│   ├── collect_news.py          # Google News RSS (gratuit)
│   ├── collect_price.py         # prix + volume via Yahoo Finance (gratuit)
│   ├── collect_stocktwits.py    # sentiment social (gratuit)
│   ├── collect_grok_sentiment.py # sentiment X réel via Grok Live Search (PAYANT, optionnel)
│   ├── send_email.py            # rapport par email (SMTP, optionnel)
│   ├── scoring.py               # combine les signaux en un score composite
│   └── run_all.py               # orchestrateur, point d'entrée
├── dashboard/
│   └── index.html               # dashboard statique
├── data/
│   ├── output.json              # dernier résultat (lu par le dashboard)
│   └── history/                 # archive des runs précédents
└── .github/workflows/update.yml # planification + déploiement automatiques
```

## Comment le score est calculé

Chaque signal est normalisé sur 100 (relatif au max de la watchlist du jour),
puis combiné selon les poids définis dans `config.py` (`WEIGHTS`) :

- 25% sentiment X réel (Grok Live Search, **payant**, 0 si `GROK_API_KEY`
  non configuré — cf. section 7 de l'installation)
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
- Backtester le score : croiser `data/history/` avec le cours réel des
  jours suivants pour vérifier empiriquement que le score précède de vrais
  mouvements, plutôt que de le supposer
