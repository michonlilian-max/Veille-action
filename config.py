"""
Configuration centrale : watchlist, pondération du score, réglages divers.

Personnalise au minimum SEC_USER_AGENT et WATCHLIST avant de déployer
(voir README.md, section "Installation").
"""

# La SEC exige un User-Agent identifiable (nom + email) sur toutes les
# requêtes EDGAR, sinon elle bloque l'IP qui fait la requête.
# Remplace par tes propres informations.
SEC_USER_AGENT = "Ton Nom ton.email@example.com"

# Liste fixe des tickers suivis. Pas de découverte automatique de tickers
# "trending" gratuitement (cf. README) — ajoute/retire ce qui t'intéresse.
WATCHLIST = [
    "AAPL",
    "MSFT",
    "NVDA",
    "TSLA",
    "AMZN",
    "GOOGL",
    "META",
    "AMD",
    "PLTR",
    "GME",
]

# Pondération des signaux dans le score composite (doit sommer à 1.0).
WEIGHTS = {
    "sentiment_social": 0.35,
    "news": 0.25,
    "insider_buying": 0.25,
    "institutional_13f": 0.15,
}

# Fenêtre de temps (en jours) pour considérer un Form 4 comme "récent".
INSIDER_LOOKBACK_DAYS = 30

# Fenêtre de temps (en jours) pour considérer un 13F-HR comme "récent".
# Le 13F a 45 jours de retard légal de dépôt (cf. README) : on ajoute une
# marge pour ne pas rater les dépôts publiés au dernier moment.
FILING_13F_LOOKBACK_DAYS = 45 + 30

# Nombre max d'articles de news conservés par ticker.
NEWS_MAX_ITEMS = 20

# Fenêtre de temps (en jours) pour compter une news comme "récente".
NEWS_LOOKBACK_DAYS = 3

# Timeout par défaut (secondes) pour les requêtes HTTP.
REQUEST_TIMEOUT = 15
