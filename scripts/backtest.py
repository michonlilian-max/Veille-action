"""
Phase d'autocritique, exécutée après la clôture des marchés US (cf.
.github/workflows/backtest.yml) : compare le score calculé CE MATIN pour
le top GROK_TOP_N (cf. config.py) au mouvement RÉEL survenu ce jour-là,
et journalise ça dans data/backtest/ pour accumuler assez d'observations
avant de tirer une quelconque conclusion.

Objectif explicite (demande utilisateur) : identifier lesquels des 6
signaux corrèlent réellement avec un mouvement de prix POSITIF le
lendemain — pas juste avec "plus d'attention" (ce que le score mesure
aujourd'hui, cf. scoring.py). C'est un objectif plus dur et plus casse-
gueule que le score d'attention actuel :

- Un seul jour (30 tickers) ne veut RIEN dire statistiquement — le bruit
  de marché domine largement un échantillon aussi petit. Rien n'est
  affiché tant que MIN_BACKTEST_SAMPLES observations ne sont pas
  accumulées (cf. config.py, quelques semaines de runs quotidiens).
- Tous les signaux ne sont pas censés être directionnels par construction.
  insider_buying (achat réel en marché ouvert) est le plus crédible ;
  volume_spike/news_volume captent de l'attention dans n'importe quel
  sens (un ticker peut exploser en volume sur une MAUVAISE nouvelle) —
  s'attendre à ce qu'ils "prédisent la hausse" est probablement optimiste,
  mais autant le mesurer plutôt que de le supposer.
- Ce module ne modifie JAMAIS config.WEIGHTS tout seul. Il journalise et
  résume ; c'est un humain qui décide de rééquilibrer les poids après
  avoir vu des semaines de données réelles (cf. README).
"""
import glob
import json
import os
import statistics
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BACKTEST_RETENTION_DAYS, GROK_TOP_N, MIN_BACKTEST_SAMPLES, WEIGHTS
from scripts.collect_price import collect_all_prices
from scripts.history_utils import find_morning_snapshot

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_DIR = os.path.join(ROOT, "data", "history")
BACKTEST_DIR = os.path.join(ROOT, "data", "backtest")
SUMMARY_PATH = os.path.join(ROOT, "data", "backtest_summary.json")

# Signaux normalisés (0-100) présents dans chaque row de "detail", + le
# score composite lui-même — ce sont les colonnes qu'on met à l'épreuve.
SIGNALS = list(WEIGHTS.keys()) + ["score"]


def _prune_backtest_log():
    cutoff = datetime.now(timezone.utc) - timedelta(days=BACKTEST_RETENTION_DAYS)
    for path in glob.glob(os.path.join(BACKTEST_DIR, "*.json")):
        stamp = os.path.basename(path).rsplit(".", 1)[0]  # "2026-08-21"
        try:
            file_dt = datetime.strptime(stamp, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if file_dt < cutoff:
            os.remove(path)
            print(f"[backtest] Journal expiré supprimé : {os.path.basename(path)}")


def _load_accumulated_log() -> list[dict]:
    """Charge tous les jours journalisés encore dans la fenêtre de
    rétention (chaque fichier = un jour, cf. run_backtest)."""
    days = []
    for path in sorted(glob.glob(os.path.join(BACKTEST_DIR, "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                days.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    return days


def _compute_summary(days: list[dict]) -> dict | None:
    """Pour chaque signal : corrélation (predicted vs mouvement réel signé)
    + comparaison "signal élevé vs signal faible vs taux de base du marché
    ce jour-là" sur l'ensemble des jours accumulés. Renvoie None si pas
    encore assez d'observations (cf. MIN_BACKTEST_SAMPLES)."""
    total_n = sum(len(d.get("entries", [])) for d in days)
    if total_n < MIN_BACKTEST_SAMPLES:
        print(f"[backtest] {total_n}/{MIN_BACKTEST_SAMPLES} observations accumulées — pas encore assez pour un résumé fiable.")
        return None

    base_rates = [d["base_rate"]["pct_positive"] for d in days if d.get("base_rate")]
    market_base_rate = round(statistics.mean(base_rates), 1) if base_rates else None

    per_signal = {}
    for signal in SIGNALS:
        pairs = []       # (valeur prédite, mouvement réel signé) sur tous les jours
        high_positive = 0
        high_total = 0
        low_positive = 0
        low_total = 0

        for day in days:
            entries = [e for e in day.get("entries", []) if e.get("actual_change_pct") is not None]
            values = [e["predicted_detail"].get(signal) if signal != "score" else e["predicted_score"] for e in entries]
            values = [v for v in values if v is not None]
            if not values:
                continue
            day_median = statistics.median(values)

            for e in entries:
                v = e["predicted_detail"].get(signal) if signal != "score" else e["predicted_score"]
                if v is None:
                    continue
                actual = e["actual_change_pct"]
                pairs.append((v, actual))
                if v >= day_median:
                    high_total += 1
                    high_positive += 1 if actual > 0 else 0
                else:
                    low_total += 1
                    low_positive += 1 if actual > 0 else 0

        if len(pairs) < 2:
            continue
        predicted_vals = [p[0] for p in pairs]
        actual_vals = [p[1] for p in pairs]
        try:
            correlation = round(statistics.correlation(predicted_vals, actual_vals), 3)
        except statistics.StatisticsError:
            correlation = None  # variance nulle (ex: signal toujours à 0)

        per_signal[signal] = {
            "n": len(pairs),
            "correlation_with_next_day_return": correlation,
            "hit_rate_when_high_pct": round(100 * high_positive / high_total, 1) if high_total else None,
            "hit_rate_when_low_pct": round(100 * low_positive / low_total, 1) if low_total else None,
        }

    return {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "total_observations": total_n,
        "days_covered": len(days),
        "top_n_per_day": GROK_TOP_N,
        "market_base_rate_pct_positive": market_base_rate,
        "signals": per_signal,
        "note": (
            "hit_rate_when_high_pct / _low_pct : proportion de tickers avec un "
            "mouvement réel positif le jour suivant, parmi ceux où ce signal était "
            "au-dessus / en-dessous de la médiane du jour (top GROK_TOP_N). À "
            "comparer à market_base_rate_pct_positive (taux de base sur toute la "
            "watchlist ce jour-là) — un hit_rate proche du taux de base veut dire "
            "que le signal n'apporte pas d'avantage directionnel mesurable."
        ),
    }


def run_backtest():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    snapshot = find_morning_snapshot(today)
    if snapshot is None:
        print(f"[backtest] Aucun run de nuit trouvé pour aujourd'hui ({today}) — backtest ignoré.")
        return

    top_rows = snapshot["watchlist"][:GROK_TOP_N]
    top_tickers = [row["ticker"] for row in top_rows]

    print(f"[backtest] Récupération du mouvement réel du jour pour {len(top_tickers)} tickers (top du run de ce matin)...")
    actual_top = collect_all_prices(watchlist=top_tickers)

    full_watchlist_tickers = [row["ticker"] for row in snapshot["watchlist"]]
    print(f"[backtest] Récupération du taux de base marché sur {len(full_watchlist_tickers)} tickers...")
    actual_full = collect_all_prices(watchlist=full_watchlist_tickers)

    positive = sum(1 for v in actual_full.values() if v.get("change_pct") is not None and v["change_pct"] > 0)
    total = sum(1 for v in actual_full.values() if v.get("change_pct") is not None)
    base_rate = {
        "positive_count": positive,
        "total_count": total,
        "pct_positive": round(100 * positive / total, 1) if total else None,
    }

    entries = []
    for row in top_rows:
        t = row["ticker"]
        a = actual_top.get(t)
        entries.append({
            "ticker": t,
            "predicted_score": row["score"],
            "predicted_detail": row["detail"],
            "actual_change_pct": a["change_pct"] if a else None,
            "actual_volume_ratio": a["volume_ratio"] if a else None,
        })

    day_record = {
        "date": today,
        "reference_run": snapshot["generated_at"],
        "base_rate": base_rate,
        "entries": entries,
    }

    os.makedirs(BACKTEST_DIR, exist_ok=True)
    day_path = os.path.join(BACKTEST_DIR, f"{today}.json")
    with open(day_path, "w", encoding="utf-8") as f:
        json.dump(day_record, f, ensure_ascii=False, indent=2)
    print(f"[backtest] Journal du jour écrit : {day_path}")

    _prune_backtest_log()

    days = _load_accumulated_log()
    summary = _compute_summary(days)
    if summary:
        with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"[backtest] Résumé mis à jour ({summary['total_observations']} observations) : {SUMMARY_PATH}")
        for signal, stats in summary["signals"].items():
            print(f"  {signal}: r={stats['correlation_with_next_day_return']}, "
                  f"hit_rate_high={stats['hit_rate_when_high_pct']}%, "
                  f"hit_rate_low={stats['hit_rate_when_low_pct']}% "
                  f"(base marché={summary['market_base_rate_pct_positive']}%)")


if __name__ == "__main__":
    run_backtest()
