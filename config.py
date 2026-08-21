"""
Configuration centrale du projet de veille boursière.
"""
import sys

from scripts.fetch_sp500 import fetch_sp500_tickers

# --- Univers de repli (90 tickers, 15 par secteur) ---
# Utilisé UNIQUEMENT si la récupération dynamique du S&P 500 ci-dessous
# échoue (source indisponible, format changé, réponse tronquée...) —
# mieux vaut un univers réduit mais garanti correct qu'un univers large
# et potentiellement faux. cf. scripts/fetch_sp500.py.
#
# Note : CRCL (Circle), SOFI (SoFi) et RKLB (Rocket Lab) de l'ancienne
# liste ne rentrent dans aucun des 6 secteurs demandés (fintech/aérospatial)
# et ont été retirés. Dis-le si tu veux les remettre.
FALLBACK_WATCHLIST = [
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

# --- Univers réel suivi par le pipeline : S&P 500, récupéré dynamiquement ---
# Remplace l'ancienne liste figée à la main (91 -> ~500 tickers). Le S&P
# 500 est recomposé plusieurs fois par an : une liste statique deviendrait
# obsolète en quelques mois. cf. scripts/fetch_sp500.py pour la source et
# la logique de repli.
_sp500 = fetch_sp500_tickers()
if _sp500:
    WATCHLIST = _sp500
    print(f"[config] Univers suivi : S&P 500 ({len(WATCHLIST)} tickers).", file=sys.stderr)
else:
    WATCHLIST = FALLBACK_WATCHLIST
    print(
        f"[config] Récupération S&P 500 échouée — repli sur la liste "
        f"manuelle ({len(WATCHLIST)} tickers).",
        file=sys.stderr,
    )

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
# Le vrai levier pour la pertinence, c'est FRESHNESS_HOURS ci-dessus.
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
GROK_MAX_SEARCH_RESULTS = 8

# Nombre de tickers effectivement envoyés à Grok (signal X, payant) à
# chaque run : uniquement les GROK_TOP_N mieux classés sur les signaux
# GRATUITS (un pré-score est calculé sans le signal X, cf. run_all.py).
# Ça borne le coût du seul signal payant du pipeline à une valeur fixe,
# indépendante de la taille de WATCHLIST — indispensable maintenant que
# celle-ci peut valoir ~500 (S&P 500) plutôt que 90. Voir le README
# (section 7) pour l'estimation de coût correspondante.
GROK_TOP_N = 30

# Nombre de jours de conservation des instantanés dans data/history/ avant
# suppression automatique par run_all.py. Un instantané S&P 500 pèse ~5x
# plus qu'un instantané à 90 tickers (plus de tickers = plus de données
# brutes) — sans purge, le dépôt grossirait de plusieurs centaines de Mo
# par an rien qu'avec ces archives.
HISTORY_RETENTION_DAYS = 30

# Nombre de jours de conservation du journal de backtest (data/backtest/,
# cf. scripts/backtest.py) avant suppression automatique. Plus long que
# HISTORY_RETENTION_DAYS : il faut des mois de recul pour qu'une
# corrélation par signal soit autre chose que du bruit statistique.
BACKTEST_RETENTION_DAYS = 180

# Nombre minimum d'observations (tickers × jours) accumulées dans le
# journal de backtest avant d'afficher/écrire une quelconque conclusion
# sur la fiabilité directionnelle d'un signal. 300 ≈ 10 jours de bourse à
# GROK_TOP_N=30 tickers/jour — en dessous, une corrélation observée ne
# veut rien dire (bruit de marché >> taille d'échantillon).
MIN_BACKTEST_SAMPLES = 300

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
