"""
Point d'entrée unique : collecte toutes les sources, calcule le score composite,
écrit data/output.json (lu par le dashboard) et archive un instantané daté dans
data/history/.

Usage : python scripts/run_all.py
Exécuté automatiquement par .github/workflows/update.yml toutes les X heures.
"""
import sys
import os
import json
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.collect_edgar import collect_insider_trades, collect_13f_filings
from scripts.collect_news import collect_all_news
from scripts.collect_stocktwits import collect_all_sentiment
from scripts.scoring import build_scores

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(ROOT, "data", "output.json")
HISTORY_DIR = os.path.join(ROOT, "data", "history")


def main():
    print("Collecte SEC EDGAR (Form 4 + 13F)...")
    insider_filings = collect_insider_trades()
    filings_13f = collect_13f_filings()

    print("Collecte des news...")
    news_data = collect_all_news()

    print("Collecte du sentiment StockTwits...")
    sentiment_data = collect_all_sentiment()

    print("Calcul des scores...")
    scores = build_scores(sentiment_data, news_data, insider_filings, filings_13f)

    timestamp = datetime.now(timezone.utc).isoformat()
    output = {
        "generated_at": timestamp,
        "watchlist": scores,
        "raw": {
            "insider_filings_sample": insider_filings[:15],
            "filings_13f_sample": filings_13f[:15],
        },
        "disclaimer": (
            "Ceci n'est pas un conseil en investissement. Score d'attention relative "
            "basé sur des signaux publics gratuits (sentiment social, news, dépôts SEC). "
            "À croiser avec ta propre analyse."
        ),
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    os.makedirs(HISTORY_DIR, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    history_file = os.path.join(HISTORY_DIR, f"{timestamp[:13].replace(':', '-')}.json")
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Terminé. {len(scores)} tickers scorés. Écrit dans {OUTPUT_PATH}")
    print("Top 5 :")
    for row in scores[:5]:
        print(f"  {row['ticker']}: {row['score']}")


if __name__ == "__main__":
    main()
