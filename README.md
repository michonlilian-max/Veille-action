# Veille Actions — watchlist automatisée, 100% gratuite

Une petite application qui croise trois signaux publics et gratuits pour
repérer les actions à surveiller :

1. **Sentiment social** via l'API publique gratuite de StockTwits (substitut
   à X/Twitter, dont l'API payante est hors budget)
2. **Actualité financière** via le flux RSS gratuit de Google News
3. **Mouvements des initiés et des grands investisseurs** via SEC EDGAR
   (Form 4 = achats/ventes des dirigeants, 13F-HR = positions institutionnelles)

Le tout tourne **gratuitement** sur GitHub Actions (planification automatique)
et s'affiche sur un dashboard statique hébergé par GitHub Pages (gratuit).

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
demandé. Le fichier `.github/workflows/update.yml` est déjà configuré pour
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

---

## Structure du projet

```
veille-actions/
├── config.py                    # watchlist, pondérations du score, réglages
├── requirements.txt
├── scripts/
│   ├── collect_edgar.py         # Form 4 + 13F via SEC EDGAR (gratuit)
│   ├── collect_news.py          # Google News RSS (gratuit)
│   ├── collect_stocktwits.py    # sentiment social (gratuit)
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

- 35% sentiment social (ratio bullish/bearish StockTwits, pondéré par le volume)
- 25% volume de news récentes
- 25% présence dans des Form 4 récents (achats/ventes d'initiés)
- 15% présence dans un 13F récent

Ajuste ces poids librement selon ce que tu veux privilégier.

## Prochaines améliorations possibles

- Alertes email/Telegram quand un ticker dépasse un seuil de score (gratuit
  avec GitHub Actions + un webhook)
- Distinguer achat vs vente dans les Form 4 (actuellement on compte juste
  les mentions — le détail acheteur/vendeur demande de parser le XML du
  filing individuel, pas juste le flux "getcurrent")
- Ajouter Reddit (r/wallstreetbets, r/stocks) comme 2e source de sentiment
  social gratuite, en complément de StockTwits
