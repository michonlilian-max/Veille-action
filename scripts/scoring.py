"""
Combine les signaux collectés (sentiment social, news, insiders, 13F) en un
score composite par ticker, normalisé sur 100.

Le score n'est PAS une prédiction — c'est un indicateur d'attention relative,
pour repérer rapidement ce qui bouge plus que d'habitude.
"""
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (
    INSIDER_DECAY_HALF_LIFE_HOURS,
    NEWS_DECAY_HALF_LIFE_HOURS,
    WATCHLIST,
    WEIGHTS,
)
from scripts.decay import decay_weight, hours_since_date, hours_since_rfc822


def _normalize(values: dict[str, float]) -> dict[str, float]:
    """Ramène un dict {ticker: valeur} sur une échelle 0-100 (max = 100)."""
    if not values:
        return {}
    max_v = max(values.values()) or 1
    return {k: round((v / max_v) * 100, 1) for k, v in values.items()}


def _price_volume_raw(entry):
    """Score brut basé sur le ratio volume du jour / volume moyen, avec un
    bonus si le prix bouge fort (dans un sens ou dans l'autre — c'est un
    signal d'attention, pas un signal directionnel achat/vente)."""
    if not entry:
        return 0.0
    volume_ratio = entry.get("volume_ratio", 1.0)
    change_pct = abs(entry.get("change_pct", 0.0))
    return volume_ratio * (1 + min(change_pct, 20) / 20)


def _x_sentiment_raw(entry):
    """Score brut du sentiment X (Grok Live Search) : même formule que le
    signal StockTwits (ratio bullish pondéré par le volume de posts), pour
    rester cohérent entre les deux sources de sentiment social."""
    if not entry:
        return 0.0
    bullish = entry.get("bullish", 0)
    bearish = entry.get("bearish", 0)
    total = bullish + bearish
    if not total:
        return 0.0
    ratio = bullish / total
    post_count = entry.get("post_count", total)
    return ratio * (1 + min(post_count, 30) / 30)


def build_scores(sentiment_data: list[dict], news_data: dict[str, list[dict]],
                  insider_filings: list[dict], filings_13f: list[dict],
                  price_data: dict[str, dict] | None = None,
                  x_sentiment_data: dict[str, dict] | None = None) -> list[dict]:
    price_data = price_data or {}
    x_sentiment_data = x_sentiment_data or {}
    now = datetime.now(timezone.utc)

    # --- signal 1 : sentiment social (ratio bullish, pondéré par le volume) ---
    sentiment_raw = {}
    for row in sentiment_data:
        t = row["ticker"]
        total = row.get("total_messages", 0)
        bullish = row.get("bullish", 0)
        ratio = (bullish / total) if total else 0
        sentiment_raw[t] = ratio * (1 + min(total, 30) / 30)  # bonus léger si volume élevé

    # --- signal 2 : volume de news récentes, pondéré par fraîcheur ---
    # Un article publié il y a 2h ne compte plus pareil qu'un article en
    # fin de fenêtre FRESHNESS_HOURS — son poids décroît avec son âge
    # (cf. scripts/decay.py, config.NEWS_DECAY_HALF_LIFE_HOURS). Le
    # compte brut (news_count, affiché tel quel sur le dashboard/email)
    # reste séparé : la pondération ne sert qu'au score.
    news_count_raw = {t: len(articles) for t, articles in news_data.items()}
    news_raw = {}
    for t, articles in news_data.items():
        total_weight = 0.0
        for article in articles:
            age = hours_since_rfc822(article.get("published", ""), now)
            total_weight += decay_weight(age, NEWS_DECAY_HALF_LIFE_HOURS) if age is not None else 1.0
        news_raw[t] = total_weight

    # --- signal 3 : vrais achats d'initiés en marché ouvert (Form 4, code P) ---
    # collect_edgar.py résout le CIK de chaque société, attribue chaque
    # dépôt à son ticker (champ "ticker") et classe achat/vente/autre en
    # parsant le XML individuel (champ "transaction_type"). On ne compte
    # ici que les vrais achats — les ventes et le bruit (attributions,
    # exercices d'options, retenues fiscales) ne comptent plus comme un
    # signal positif, ce qui corrige le mislabeling de l'ancienne version
    # (qui comptait tout Form 4 confondu sous "insider_buying").
    # Pondéré par fraîcheur comme les news ci-dessus : un achat d'hier
    # pèse plus qu'un achat vieux de 29 jours (cf.
    # config.INSIDER_DECAY_HALF_LIFE_HOURS) — avant, les deux comptaient
    # exactement pareil tant qu'ils étaient dans INSIDER_LOOKBACK_DAYS.
    insider_raw = {t: 0.0 for t in WATCHLIST}
    for filing in insider_filings:
        t = filing.get("ticker")
        if t in insider_raw and filing.get("transaction_type") == "buy":
            age = hours_since_date(filing.get("filing_date", ""), now)
            insider_raw[t] += decay_weight(age, INSIDER_DECAY_HALF_LIFE_HOURS) if age is not None else 1.0

    # --- signal 4 : 13F-HR récents mentionnant la société, par ticker ---
    inst_raw = {t: 0 for t in WATCHLIST}
    for filing in filings_13f:
        t = filing.get("ticker")
        if t in inst_raw:
            inst_raw[t] += 1

    # --- signal 5 : volume d'échange anormal + amplitude de prix (Yahoo Finance) ---
    price_raw = {t: _price_volume_raw(price_data.get(t)) for t in WATCHLIST}

    # --- signal 6 : sentiment X réel via Grok Live Search (payant, optionnel) ---
    # x_sentiment_data est vide si GROK_API_KEY n'est pas configuré — le
    # signal contribue alors 0 partout, comme les autres signaux absents.
    x_raw = {t: _x_sentiment_raw(x_sentiment_data.get(t)) for t in WATCHLIST}

    sentiment_n = _normalize(sentiment_raw)
    news_n = _normalize(news_raw)
    insider_n = _normalize(insider_raw)
    inst_n = _normalize(inst_raw)
    price_n = _normalize(price_raw)
    x_n = _normalize(x_raw)

    results = []
    for t in WATCHLIST:
        score = (
            WEIGHTS["sentiment_social"] * sentiment_n.get(t, 0)
            + WEIGHTS["news_volume"] * news_n.get(t, 0)
            + WEIGHTS["insider_buying"] * insider_n.get(t, 0)
            + WEIGHTS["institutional_13f"] * inst_n.get(t, 0)
            + WEIGHTS["volume_spike"] * price_n.get(t, 0)
            + WEIGHTS["sentiment_x"] * x_n.get(t, 0)
        )
        p = price_data.get(t) or {}
        x = x_sentiment_data.get(t) or {}
        results.append({
            "ticker": t,
            "score": round(score, 1),
            "detail": {
                "sentiment_social": sentiment_n.get(t, 0),
                "news_volume": news_n.get(t, 0),
                "insider_buying": insider_n.get(t, 0),
                "institutional_13f": inst_n.get(t, 0),
                "volume_spike": price_n.get(t, 0),
                "sentiment_x": x_n.get(t, 0),
            },
            "news_count": news_count_raw.get(t, 0),
            "price": p.get("price"),
            "change_pct": p.get("change_pct"),
            "volume_ratio": p.get("volume_ratio"),
            "x_summary": x.get("summary"),
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results
