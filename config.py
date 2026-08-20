"""
Configuration centrale du projet de veille boursière.
Modifie WATCHLIST pour suivre les tickers qui t'intéressent.
"""

# Liste des tickers à surveiller, organisée par secteur — 15 par secteur
# (StockTwits n'offre plus de découverte "trending" fiable en accès
# gratuit -> on part d'une liste définie).
#
# Note : CRCL (Circle), SOFI (SoFi) et RKLB (Rocket Lab) de l'ancienne
# liste ne rentrent dans aucun des 6 secteurs demandés (fintech/aérospatial)
# et ont été retirés. Dis-le si tu veux les remettre.
WATCHLIST = [
    # --- Biotechnologie (15) ---
    "MRNA", "VRTX", "REGN", "AMGN", "GILD", "BIIB", "ILMN", "ALNY",
    "BMRN", "INCY", "NVAX", "EXEL", "SRPT", "IONS", "NBIX",
    # --- Énergie (15) ---
    "XOM", "CVX", "NEE", "COP", "SLB", "EOG", "PSX", "MPC", "OXY",
    "WMB", "KMI", "DVN", "HES", "FANG", "VLO",
    # --- Semi-conducteurs (15) ---
    "NVDA", "AMD", "MU", "INTC", "TSM", "AVGO", "ARM", "QCOM", "TXN",
    "ASML", "LRCX", "KLAC", "MRVL", "ON", "MCHP",
    # --- Électronique (15) ---
    "APH", "TEL", "KEYS", "FTV", "GRMN", "LOGI", "SONY", "HON", "EMR",
    "ROK", "ZBRA", "CIEN", "FLEX", "JBL", "VSH",
    # --- Technologie (15) ---
    "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "ORCL",
    "CRM", "ADBE", "NOW", "INTU", "SHOP", "UBER", "IBM",
    # --- Intelligence artificielle (15) ---
    "PLTR", "NBIS", "SMCI", "AI", "PATH", "SOUN", "BBAI", "UPST",
    "SNOW", "DDOG", "MDB", "CFLT", "ESTC", "IOT", "TEM",
]

# User-Agent obligatoire pour interroger SEC EDGAR (politique SEC "fair access").
SEC_USER_AGENT = "Veille Actions (contact: michonlilian@yahoo.fr)"

# Fenêtre (en jours) pour considérer un Form 4 comme "récent".
INSIDER_LOOKBACK_DAYS = 30

# Fenêtre (en jours) pour la recherche de 13F-HR récents. Le 13F a 45 jours
# de retard légal de dépôt (cf. README) : on ajoute une marge pour ne pas
# rater les dépôts publiés au dernier moment.
FILING_13F_LOOKBACK_DAYS = 90

# Fenêtre (en heures) pour ne garder que les news récentes (collect_news.py
# rejette tout article plus vieux que ça). 72h = 3 jours.
FRESHNESS_HOURS = 72

# Nombre max d'articles Google News regardés par ticker (avant filtrage par
# fraîcheur). ⚠️ Google News RSS ne renvoie quasiment jamais plus d'une
# centaine de résultats par requête, quel que soit ce plafond — le monter à
# 300 ne fera donc pas nécessairement remonter plus d'articles en pratique.
# Le vrai levier pour la pertinence, c'est FRESHNESS_HOURS ci-dessus : en
# ne gardant que les 3 derniers jours, le compte par ticker redevient
# variable (certains tickers ont eu beaucoup d'actu récente, d'autres non)
# au lieu de plafonner tous au même nombre.
NEWS_MAX_ITEMS = 300

# Fenêtre (en jours) d'historique de prix/volume téléchargée (Yahoo
# Finance). Doit être assez large pour calculer un volume moyen
# significatif — 30 jours de bourse ≈ 20 jours ouvrés.
PRICE_VOLUME_LOOKBACK_DAYS = 30

# Modèle xAI utilisé pour l'analyse de sentiment X (Live Search). Vérifie
# les modèles disponibles et leurs tarifs sur https://console.x.ai avant
# de changer — un modèle plus gros coûte plus cher par appel.
GROK_MODEL = "grok-4-fast"

# Nombre max de posts X que Grok peut consulter par ticker (Live Search).
# Facturé par source récupérée : plus haut = plus précis mais plus cher.
# Reste volontairement bas par défaut — voir le README pour une estimation
# de coût avant d'augmenter.
GROK_MAX_SEARCH_RESULTS = 8

# Pondération du score composite (score final = somme pondérée, voir
# scoring.py). Doit sommer à 1.0.
WEIGHTS = {
    "sentiment_x": 0.25,         # sentiment X réel via Grok Live Search (payant, cf. README)
    "volume_spike": 0.20,        # volume anormal + amplitude de variation du prix
    "sentiment_social": 0.15,    # StockTwits bullish/bearish
    "news_volume": 0.15,         # nombre d'articles récents
    "insider_buying": 0.15,      # vrais achats d'initiés en marché ouvert (Form 4, code P)
    "institutional_13f": 0.10,   # apparition dans un 13F récent
}
