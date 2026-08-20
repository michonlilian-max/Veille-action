"""
Configuration centrale du projet de veille boursière.
Modifie WATCHLIST pour suivre les tickers qui t'intéressent.
"""

# Liste des tickers à surveiller en priorité (StockTwits n'offre plus de
# découverte "trending" fiable en accès gratuit -> on part d'une liste
# définie, complétée par ce qui ressort des news).
WATCHLIST = [
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "NVDA", "TSLA", "META",
    "AMD", "PLTR", "MU", "INTC", "NBIS", "CRCL", "SOFI", "RKLB",
]

# User-Agent obligatoire pour interroger SEC EDGAR (politique SEC "fair access").
SEC_USER_AGENT = "Veille Actions (contact: michonlilian@yahoo.fr)"

# Fenêtre (en jours) pour considérer un Form 4 comme "récent".
INSIDER_LOOKBACK_DAYS = 30

# Fenêtre (en jours) pour la recherche de 13F-HR récents. Le 13F a 45 jours
# de retard légal de dépôt (cf. README) : on ajoute une marge pour ne pas
# rater les dépôts publiés au dernier moment.
FILING_13F_LOOKBACK_DAYS = 90

# Fenêtre (en heures) pour considérer une actu ou un post comme "récent".
FRESHNESS_HOURS = 48

# Fenêtre (en jours) d'historique de prix/volume téléchargée (Yahoo
# Finance). Doit être assez large pour calculer un volume moyen
# significatif — 30 jours de bourse ≈ 20 jours ouvrés.
PRICE_VOLUME_LOOKBACK_DAYS = 30

# Pondération du score composite (score final = somme pondérée, voir
# scoring.py). Doit sommer à 1.0.
WEIGHTS = {
    "sentiment_social": 0.25,   # StockTwits bullish/bearish
    "news_volume": 0.20,        # nombre d'articles récents
    "insider_buying": 0.20,     # vrais achats d'initiés en marché ouvert (Form 4, code P)
    "institutional_13f": 0.10,  # apparition dans un 13F récent
    "volume_spike": 0.25,       # volume anormal + amplitude de variation du prix
}
