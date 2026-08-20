"""
Sentiment social via l'API publique (non authentifiée) de StockTwits.

⚠️ StockTwits n'est pas X/Twitter — c'est le meilleur substitut gratuit
disponible (communauté retail/trading comparable), mais ce n'est pas la
même donnée. Son API publique n'a pas d'inscription développeur ouverte
actuellement : elle fonctionne en accès non authentifié, mais peut se
fermer sans préavis. Si ce script casse, c'est le premier endroit à
vérifier.
"""
import time

import requests

from config import WATCHLIST, REQUEST_TIMEOUT

STOCKTWITS_URL = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
HEADERS = {"User-Agent": "veille-actions/1.0 (script gratuit, usage personnel)"}


def collect_sentiment_for_ticker(ticker):
    """Récupère les derniers messages StockTwits pour un ticker et compte
    les messages taggés Bullish/Bearish (le tag de sentiment est optionnel
    et posé par l'auteur du message, la majorité des messages n'en ont
    pas)."""
    url = STOCKTWITS_URL.format(ticker=ticker)
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"  [stocktwits] {ticker}: erreur ({e})")
        return {"ticker": ticker, "bullish": 0, "bearish": 0, "volume": 0, "error": str(e)}

    messages = data.get("messages", []) or []
    bullish = 0
    bearish = 0
    for msg in messages:
        sentiment = (msg.get("entities") or {}).get("sentiment") or {}
        basic = sentiment.get("basic")
        if basic == "Bullish":
            bullish += 1
        elif basic == "Bearish":
            bearish += 1

    return {
        "ticker": ticker,
        "bullish": bullish,
        "bearish": bearish,
        "volume": len(messages),
    }


def collect_all_sentiment(watchlist=None):
    """Collecte le sentiment StockTwits pour toute la watchlist.

    Renvoie un dict {ticker: {...}} pour un accès direct par ticker
    (utilisé par scripts/scoring.py).
    """
    watchlist = watchlist or WATCHLIST
    results = {}
    for ticker in watchlist:
        results[ticker] = collect_sentiment_for_ticker(ticker)
        time.sleep(1)  # évite de spammer l'API publique
    return results


if __name__ == "__main__":
    import json

    print(json.dumps(collect_all_sentiment(), indent=2))
