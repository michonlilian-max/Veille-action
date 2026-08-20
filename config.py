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
# Remplace par ton propre nom + email avant de déployer.
SEC_USER_AGENT = "VeilleActions perso contact@example.com"

# Nombre de filings récents à récupérer par run pour Form 4 (insiders) et 13F.
SEC_MAX_FILINGS = 40

# Fenêtre (en heures) pour considérer une actu ou un post comme "récent".
FRESHNESS_HOURS = 48

# Pondération du score composite (score final = somme pondérée, voir scoring.py)
WEIGHTS = {
    "sentiment_social": 0.35,   # StockTwits bullish/bearish
    "news_volume": 0.25,        # nombre d'articles récents
    "insider_buying": 0.25,     # achats/ventes d'initiés (Form 4)
    "institutional_13f": 0.15,  # apparition dans un 13F récent
}
