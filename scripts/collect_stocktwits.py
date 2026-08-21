"""
Collecte le sentiment social via l'API publique de StockTwits (gratuite, sans clé,
limitée à 200 requêtes/heure/IP). C'est notre substitut à X/Twitter : la communauté
StockTwits est comparable (retail + traders), et l'API X payante est hors budget.

Doc (non officielle, l'inscription développeur StockTwits est fermée mais les
endpoints publics restent accessibles) : https://api.stocktwits.com/api/2/...

Si cet endpoint change ou se ferme, c'est le point le plus fragile du pipeline —
prévoir une alternative (Reddit API gratuite, ou scraping léger) en secours.
"""
import sys
import os
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import WATCHLIST

STREAM_URL = "https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json"
# 3600s / 200 requêtes = 18s pour être pile à la limite ; on prend 20s pour
# rester à 180/h avec une marge de sécurité. À 90 tickers (ancienne
# watchlist), un délai de 1.5s suffisait car le total restait sous 200
# quelle que soit la cadence. Depuis le passage au S&P 500 (~500 tickers,
# cf. config.py), ce n'est plus vrai : 500 appels à 1.5s d'intervalle
# tiennent en 12 minutes, largement plus de 200/h — d'où ce délai qui
# respecte la limite quelle que soit la taille de la watchlist, au prix
# d'une collecte StockTwits qui prend ~2h45 pour 500 tickers (acceptable
# sur un run de nuit, cf. README).
RATE_LIMIT_DELAY = 20


def collect_sentiment_for_ticker(ticker: str) -> dict:
    url = STREAM_URL.format(symbol=ticker)
    headers = {"User-Agent": "Mozilla/5.0 (VeilleActions personal project)"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[collect_stocktwits] Erreur pour {ticker} : {e}", file=sys.stderr)
        return {"ticker": ticker, "bullish": 0, "bearish": 0, "total_messages": 0, "error": str(e)}

    messages = data.get("messages", [])
    bullish = sum(
        1 for m in messages
        if (m.get("entities", {}).get("sentiment") or {}).get("basic") == "Bullish"
    )
    bearish = sum(
        1 for m in messages
        if (m.get("entities", {}).get("sentiment") or {}).get("basic") == "Bearish"
    )
    return {
        "ticker": ticker,
        "bullish": bullish,
        "bearish": bearish,
        "total_messages": len(messages),
    }


def collect_all_sentiment() -> list[dict]:
    results = []
    for ticker in WATCHLIST:
        results.append(collect_sentiment_for_ticker(ticker))
        time.sleep(RATE_LIMIT_DELAY)
    return results


if __name__ == "__main__":
    for r in collect_all_sentiment():
        print(r)
