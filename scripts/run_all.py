"""
Point d'entrée unique : collecte toutes les sources, calcule le score composite,
écrit data/output.json (lu par le dashboard) et archive un instantané daté dans
data/history/.

Usage : python scripts/run_all.py
Exécuté automatiquement par .github/workflows/update.yml toutes les X heures.
"""
import sys
import os
import glob
import json
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.collect_edgar import collect_insider_trades, collect_13f_filings
from scripts.collect_grok_sentiment import collect_all_x_sentiment
from scripts.collect_news import collect_all_news
from scripts.collect_price import collect_all_prices
from scripts.collect_stocktwits import collect_all_sentiment
from scripts.scoring import build_scores
from scripts.send_email import send_report
from config import GROK_TOP_N, HISTORY_RETENTION_DAYS, WATCHLIST

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(ROOT, "data", "output.json")
HISTORY_DIR = os.path.join(ROOT, "data", "history")


def _prune_history():
    """Supprime les instantanés de data/history/ plus vieux que
    HISTORY_RETENTION_DAYS. Nécessaire depuis le passage au S&P 500 : un
    instantané pèse maintenant ~5x plus qu'à 90 tickers, et le dépôt
    grossirait de plusieurs centaines de Mo par an sans purge."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=HISTORY_RETENTION_DAYS)
    for path in glob.glob(os.path.join(HISTORY_DIR, "*.json")):
        stamp = os.path.basename(path).rsplit(".", 1)[0]  # "2026-08-20T14"
        try:
            file_dt = datetime.strptime(stamp, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)
        except ValueError:
            continue  # fichier qui ne suit pas le format attendu (ex: .gitkeep) : on l'ignore
        if file_dt < cutoff:
            os.remove(path)
            print(f"[run_all] Instantané expiré supprimé : {os.path.basename(path)}")


def main():
    print(f"Univers suivi : {len(WATCHLIST)} tickers.")

    print("Collecte SEC EDGAR (Form 4 + 13F)...")
    insider_filings = collect_insider_trades()
    filings_13f = collect_13f_filings()

    print("Collecte des news...")
    news_data = collect_all_news()

    print("Collecte du sentiment StockTwits...")
    sentiment_data = collect_all_sentiment()

    print("Collecte des prix et volumes (Yahoo Finance)...")
    price_data = collect_all_prices()

    # --- Sentiment X (Grok, seul signal payant) : ciblé, pas systématique ---
    # On calcule d'abord un pré-score sans le signal X (comme s'il était
    # absent), puis on n'interroge Grok que pour les GROK_TOP_N tickers les
    # mieux classés sur les signaux gratuits. Le coût du signal payant
    # reste ainsi constant, indépendant de la taille de WATCHLIST (~500
    # avec le S&P 500, contre 90 avant) — cf. config.py et le README.
    print("Pré-score (sans le signal X) pour cibler Grok...")
    pre_scores = build_scores(sentiment_data, news_data, insider_filings, filings_13f, price_data)
    grok_targets = [row["ticker"] for row in pre_scores[:GROK_TOP_N]]

    print(f"Collecte du sentiment X (Grok Live Search, si configuré) — {len(grok_targets)} candidats ciblés...")
    x_sentiment_data = collect_all_x_sentiment(watchlist=grok_targets)

    print("Calcul des scores finaux...")
    scores = build_scores(
        sentiment_data, news_data, insider_filings, filings_13f, price_data, x_sentiment_data
    )

    # Échantillon de vrais articles, 2 par ticker sur toute la watchlist (pas
    # juste les 15 premiers d'un seul ticker) : sert de preuve vérifiable que
    # la collecte a bien ramené du contenu réel, pas juste un compteur.
    news_sample = []
    for ticker, articles in news_data.items():
        news_sample.extend(articles[:2])

    timestamp = datetime.now(timezone.utc).isoformat()
    output = {
        "generated_at": timestamp,
        "watchlist": scores,
        "raw": {
            "insider_filings_sample": insider_filings[:15],
            "filings_13f_sample": filings_13f[:15],
            "news_sample": news_sample,
            "news_count_by_ticker": {t: len(a) for t, a in news_data.items()},
            "price_data": price_data,
            "x_sentiment_data": x_sentiment_data,
        },
        "disclaimer": (
            "Ceci n'est pas un conseil en investissement. Score d'attention relative "
            "basé sur des signaux publics gratuits et un signal payant optionnel "
            "(sentiment social, news, dépôts SEC, prix/volume, sentiment X). "
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

    _prune_history()

    print(f"Terminé. {len(scores)} tickers scorés. Écrit dans {OUTPUT_PATH}")
    print("Top 5 :")
    for row in scores[:5]:
        print(f"  {row['ticker']}: {row['score']}")

    print("Envoi de l'email récapitulatif (si configuré)...")
    send_report(output)


if __name__ == "__main__":
    main()
