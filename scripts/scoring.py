"""
Combine les quatre signaux collectés en un score composite par ticker.

Chaque signal brut est normalisé sur 100, relativement au maximum observé
ce jour-là dans la watchlist (valeur / max * 100), puis les signaux
normalisés sont combinés selon les poids définis dans config.WEIGHTS :

  - 35% sentiment social (ratio bullish/bearish StockTwits, pondéré par
    le volume de messages)
  - 25% volume de news récentes
  - 25% présence dans des Form 4 récents (achats/ventes d'initiés)
  - 15% présence dans un 13F récent
"""
from collections import Counter

from config import WATCHLIST, WEIGHTS


def _sentiment_raw(sentiment_entry):
    """Score brut de sentiment social : ratio bullish/bearish pondéré par
    le volume de messages, pour éviter qu'un seul message bullish sur un
    ticker peu suivi domine le classement."""
    if not sentiment_entry:
        return 0.0
    bullish = sentiment_entry.get("bullish", 0)
    bearish = sentiment_entry.get("bearish", 0)
    volume = sentiment_entry.get("volume", 0)
    total_opinions = bullish + bearish
    if total_opinions == 0:
        return 0.0
    ratio = bullish / total_opinions  # entre 0 et 1
    return ratio * volume


def _news_raw(news_entry):
    if not news_entry:
        return 0
    return len(news_entry.get("articles", []))


def _filing_counts(filings):
    """Compte le nombre de dépôts récents par ticker."""
    counts = Counter()
    for f in filings:
        counts[f["ticker"]] += 1
    return counts


def _normalize(raw_by_ticker):
    """Normalise un dict {ticker: valeur brute} sur 100, relatif au max du
    jour. Si tous les tickers sont à zéro, renvoie 0 partout plutôt qu'une
    division par zéro."""
    max_val = max(raw_by_ticker.values()) if raw_by_ticker else 0
    if max_val <= 0:
        return {t: 0.0 for t in raw_by_ticker}
    return {t: round(v / max_val * 100, 1) for t, v in raw_by_ticker.items()}


def build_scores(sentiment_data, news_data, insider_filings, filings_13f, watchlist=None):
    """Construit la liste des tickers scorés, triée par score décroissant.

    Chaque élément a la forme attendue par dashboard/index.html :
    {"ticker": ..., "score": ..., "news_count": ..., "detail": {...}}
    """
    watchlist = watchlist or WATCHLIST

    sentiment_raw = {t: _sentiment_raw(sentiment_data.get(t)) for t in watchlist}
    news_raw = {t: _news_raw(news_data.get(t)) for t in watchlist}

    insider_raw = dict(_filing_counts(insider_filings))
    for t in watchlist:
        insider_raw.setdefault(t, 0)

    f13_raw = dict(_filing_counts(filings_13f))
    for t in watchlist:
        f13_raw.setdefault(t, 0)

    sentiment_norm = _normalize(sentiment_raw)
    news_norm = _normalize(news_raw)
    insider_norm = _normalize(insider_raw)
    f13_norm = _normalize(f13_raw)

    rows = []
    for t in watchlist:
        composite = (
            sentiment_norm[t] * WEIGHTS["sentiment_social"]
            + news_norm[t] * WEIGHTS["news"]
            + insider_norm[t] * WEIGHTS["insider_buying"]
            + f13_norm[t] * WEIGHTS["institutional_13f"]
        )
        rows.append(
            {
                "ticker": t,
                "score": round(composite, 1),
                "news_count": news_raw[t],
                "detail": {
                    "sentiment_social": sentiment_norm[t],
                    "news": news_norm[t],
                    "insider_buying": insider_norm[t],
                    "institutional_13f": f13_norm[t],
                },
            }
        )

    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows
