"""
Combine les signaux collectés (sentiment social, news, insiders, 13F) en un
score composite par ticker, normalisé sur 100.

Le score n'est PAS une prédiction — c'est un indicateur d'attention relative,
pour repérer rapidement ce qui bouge plus que d'habitude.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import WATCHLIST, WEIGHTS


def _normalize(values: dict[str, float]) -> dict[str, float]:
    """Ramène un dict {ticker: valeur} sur une échelle 0-100 (max = 100)."""
    if not values:
        return {}
    max_v = max(values.values()) or 1
    return {k: round((v / max_v) * 100, 1) for k, v in values.items()}


def build_scores(sentiment_data: list[dict], news_data: dict[str, list[dict]],
                  insider_filings: list[dict], filings_13f: list[dict]) -> list[dict]:

    # --- signal 1 : sentiment social (ratio bullish, pondéré par le volume) ---
    sentiment_raw = {}
    for row in sentiment_data:
        t = row["ticker"]
        total = row.get("total_messages", 0)
        bullish = row.get("bullish", 0)
        ratio = (bullish / total) if total else 0
        sentiment_raw[t] = ratio * (1 + min(total, 30) / 30)  # bonus léger si volume élevé

    # --- signal 2 : volume de news récentes ---
    news_raw = {t: len(articles) for t, articles in news_data.items()}

    # --- signal 3 : Form 4 récents (achats/ventes d'initiés), par ticker ---
    # collect_edgar.py résout le CIK de chaque société et attribue déjà
    # chaque dépôt à son ticker (champ "ticker") — plus de recherche de
    # texte ici, qui donnait de faux positifs sur les tickers courts
    # (ex: "MU" matchait n'importe quel mot contenant "MU").
    insider_raw = {t: 0 for t in WATCHLIST}
    for filing in insider_filings:
        t = filing.get("ticker")
        if t in insider_raw:
            insider_raw[t] += 1

    # --- signal 4 : 13F-HR récents mentionnant la société, par ticker ---
    inst_raw = {t: 0 for t in WATCHLIST}
    for filing in filings_13f:
        t = filing.get("ticker")
        if t in inst_raw:
            inst_raw[t] += 1

    sentiment_n = _normalize(sentiment_raw)
    news_n = _normalize(news_raw)
    insider_n = _normalize(insider_raw)
    inst_n = _normalize(inst_raw)

    results = []
    for t in WATCHLIST:
        score = (
            WEIGHTS["sentiment_social"] * sentiment_n.get(t, 0)
            + WEIGHTS["news_volume"] * news_n.get(t, 0)
            + WEIGHTS["insider_buying"] * insider_n.get(t, 0)
            + WEIGHTS["institutional_13f"] * inst_n.get(t, 0)
        )
        results.append({
            "ticker": t,
            "score": round(score, 1),
            "detail": {
                "sentiment_social": sentiment_n.get(t, 0),
                "news_volume": news_n.get(t, 0),
                "insider_buying": insider_n.get(t, 0),
                "institutional_13f": inst_n.get(t, 0),
            },
            "news_count": news_raw.get(t, 0),
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results
