"""
Collecte les actualités financières récentes via le flux RSS gratuit de Google News,
filtré par ticker. Pas de clé API nécessaire.

Limite connue : Google News RSS peut renvoyer des résultats bruités (articles
peu pertinents). On filtre grossièrement sur la présence du ticker/nom dans le titre.
"""
import sys
import os
import requests
import feedparser

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import WATCHLIST

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


def collect_news_for_ticker(ticker: str, max_items: int = 10) -> list[dict]:
    params = {
        "q": f"{ticker} stock",
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    }
    headers = {"User-Agent": "Mozilla/5.0 (VeilleActions RSS reader)"}
    try:
        resp = requests.get(GOOGLE_NEWS_RSS, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[collect_news] Erreur pour {ticker} : {e}", file=sys.stderr)
        return []

    feed = feedparser.parse(resp.content)
    items = []
    for entry in feed.entries[:max_items]:
        items.append({
            "ticker": ticker,
            "title": entry.get("title", ""),
            "link": entry.get("link", ""),
            "published": entry.get("published", ""),
            "source": entry.get("source", {}).get("title", "") if hasattr(entry.get("source", {}), "get") else "",
        })
    return items


def collect_all_news() -> dict[str, list[dict]]:
    """Retourne un dict {ticker: [articles]} pour toute la watchlist."""
    results = {}
    for ticker in WATCHLIST:
        results[ticker] = collect_news_for_ticker(ticker)
    return results


if __name__ == "__main__":
    all_news = collect_all_news()
    for ticker, articles in all_news.items():
        print(f"{ticker}: {len(articles)} articles")
