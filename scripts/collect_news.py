"""
Actualité financière via le flux RSS gratuit de Google News.

⚠️ Bruité par nature : certains articles retournés seront peu pertinents
(le mot-clé "ticker + stock" fait parfois remonter des articles hors
sujet). C'est un compromis du gratuit vs une vraie API news payante.
"""
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser

from config import NEWS_LOOKBACK_DAYS, NEWS_MAX_ITEMS, WATCHLIST

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=fr&gl=FR&ceid=FR:fr"


def _parse_date(entry):
    published = entry.get("published")
    if not published:
        return None
    try:
        return parsedate_to_datetime(published)
    except (TypeError, ValueError):
        return None


def collect_news_for_ticker(ticker):
    """Récupère les articles récents mentionnant le ticker via Google News
    RSS, filtrés sur la fenêtre NEWS_LOOKBACK_DAYS."""
    query = f"{ticker}+stock"
    url = GOOGLE_NEWS_RSS.format(query=query)
    try:
        feed = feedparser.parse(url)
        if getattr(feed, "bozo", False) and not feed.entries:
            raise ValueError(str(getattr(feed, "bozo_exception", "flux RSS invalide")))
    except Exception as e:
        print(f"  [news] {ticker}: erreur ({e})")
        return {"ticker": ticker, "articles": [], "error": str(e)}

    cutoff = datetime.now(timezone.utc) - timedelta(days=NEWS_LOOKBACK_DAYS)
    articles = []
    for entry in feed.entries[:NEWS_MAX_ITEMS]:
        published_dt = _parse_date(entry)
        if published_dt and published_dt < cutoff:
            continue
        articles.append(
            {
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
                "source": (entry.get("source") or {}).get("title", ""),
            }
        )

    return {"ticker": ticker, "articles": articles}


def collect_all_news(watchlist=None):
    """Collecte les news récentes pour toute la watchlist.

    Renvoie un dict {ticker: {...}} pour un accès direct par ticker
    (utilisé par scripts/scoring.py).
    """
    watchlist = watchlist or WATCHLIST
    results = {}
    for ticker in watchlist:
        results[ticker] = collect_news_for_ticker(ticker)
        time.sleep(0.5)
    return results


if __name__ == "__main__":
    import json

    print(json.dumps(collect_all_news(), indent=2))
