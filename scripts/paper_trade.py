"""
Bot de trading — EXCLUSIVEMENT en paper trading (argent fictif), jamais réel.

Utilise l'API Alpaca (https://alpaca.markets) en mode paper : rejoue les
décisions qu'un bot prendrait sur le score du matin, avec un vrai
mécanisme d'exécution d'ordres, mais sans un seul dollar réel engagé.
C'est l'étape avant tout passage à du réel — inutile (et dangereux)
d'y penser tant qu'on n'a pas des semaines/mois de résultats simulés qui
montrent que la stratégie fait mieux que le hasard (cf. scripts/backtest.py,
qui mesure la même question sous un angle différent : la fiabilité des
signaux pris isolément).

⚠️ SÉCURITÉ : `paper=True` est câblé en dur dans TradingClient ci-dessous
et n'est JAMAIS rendu configurable depuis ce fichier — il n'y a
volontairement aucun chemin de code qui permette de basculer sur le
trading réel sans modifier explicitement ce fichier. Si ALPACA_API_KEY /
ALPACA_SECRET_KEY ne sont pas configurés, ce script s'arrête proprement
sans rien faire (même logique de dégradation que send_email.py et
collect_grok_sentiment.py).

Stratégie — positions flexibles, sorties bornées (pas de "tenir 1 jour"
ni de "tout revendre chaque soir") :

1. **Entrée** (ce module, une fois par jour à l'ouverture, cf.
   .github/workflows/paper_trade.yml) : les positions déjà ouvertes (d'un
   jour précédent, pas encore sorties) sont laissées telles quelles —
   on n'achète QUE les tickers du top PAPER_TRADING_TOP_N du score du
   matin qui ne sont pas déjà en portefeuille, dans la limite des places
   libres (PAPER_TRADING_TOP_N - nombre de positions déjà tenues).
2. **Sortie** (cf. scripts/check_paper_trade_exits.py, plusieurs fois par
   jour) : chaque position est vendue dès qu'elle dépasse
   PAPER_TRADING_TAKE_PROFIT_PCT de gain OU PAPER_TRADING_STOP_LOSS_PCT
   de perte — jamais gardée indéfiniment en espérant un rebond (cf.
   config.py pour le raisonnement). Entre ces deux seuils, une position
   peut être tenue plusieurs jours.

Les deux scripts partagent le même fichier journalier dans
data/paper_trades/ et la même fonction `rebuild_summary()` pour le résumé
affiché sur le dashboard.
"""
import glob
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PAPER_TRADING_RETENTION_DAYS, PAPER_TRADING_TOP_N
from scripts.history_utils import find_morning_snapshot

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAPER_TRADES_DIR = os.path.join(ROOT, "data", "paper_trades")
SUMMARY_PATH = os.path.join(ROOT, "data", "paper_trades_summary.json")


def get_client():
    """Renvoie un TradingClient Alpaca en mode paper, ou None si les clés
    ne sont pas configurées / le paquet n'est pas installé. Point d'entrée
    partagé par tous les scripts du bot — paper=True câblé en dur ici
    aussi, voir l'avertissement de sécurité en tête de fichier."""
    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    if not api_key or not secret_key:
        print("[paper_trade] ALPACA_API_KEY / ALPACA_SECRET_KEY absents — bot ignoré (rien à faire).")
        return None
    try:
        from alpaca.trading.client import TradingClient
    except ImportError:
        print("[paper_trade] Le paquet 'alpaca-py' n'est pas installé (cf. requirements.txt) — bot ignoré.")
        return None
    return TradingClient(api_key, secret_key, paper=True)


def today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_day_record(date_str):
    """Charge (ou initialise) le journal du jour — partagé entre
    paper_trade.py (entrées) et check_paper_trade_exits.py (sorties +
    éventuel email), potentiellement appelés plusieurs fois le même jour."""
    path = os.path.join(PAPER_TRADES_DIR, f"{date_str}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"date": date_str, "entries": [], "exits": [], "equity_at_open": None, "equity_at_close": None}


def save_day_record(record):
    os.makedirs(PAPER_TRADES_DIR, exist_ok=True)
    path = os.path.join(PAPER_TRADES_DIR, f"{record['date']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    return path


def _prune_paper_trades_log():
    cutoff = datetime.now(timezone.utc) - timedelta(days=PAPER_TRADING_RETENTION_DAYS)
    for path in glob.glob(os.path.join(PAPER_TRADES_DIR, "*.json")):
        stamp = os.path.basename(path).rsplit(".", 1)[0]  # "2026-08-21"
        try:
            file_dt = datetime.strptime(stamp, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if file_dt < cutoff:
            os.remove(path)
            print(f"[paper_trade] Journal expiré supprimé : {os.path.basename(path)}")


def rebuild_summary(client):
    """Reconstruit data/paper_trades_summary.json à partir de l'état
    actuel du compte (équité, positions tenues) — appelé après chaque
    action (entrée ou sortie) pour garder le dashboard à jour."""
    account = client.get_account()
    equity = float(account.equity)
    positions = client.get_all_positions()
    holdings = [
        {
            "ticker": p.symbol,
            "unrealized_plpc": round(float(p.unrealized_plpc) * 100, 2),
            "market_value": round(float(p.market_value), 2),
        }
        for p in positions
    ]

    os.makedirs(PAPER_TRADES_DIR, exist_ok=True)
    daily_points = []
    for path in sorted(glob.glob(os.path.join(PAPER_TRADES_DIR, "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            daily_points.append({
                "date": d["date"],
                "equity_at_open": d.get("equity_at_open"),
                "equity_at_close": d.get("equity_at_close"),
                "entries": [e["ticker"] for e in d.get("entries", [])],
                "exits": [{"ticker": e["ticker"], "reason": e.get("reason"), "unrealized_plpc": e.get("unrealized_plpc")}
                          for e in d.get("exits", [])],
            })
        except (json.JSONDecodeError, OSError, KeyError):
            continue

    starting_equity = daily_points[0]["equity_at_open"] if daily_points and daily_points[0].get("equity_at_open") else equity
    summary = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "starting_equity": starting_equity,
        "current_equity": equity,
        "total_return_pct": round(100 * (equity - starting_equity) / starting_equity, 2) if starting_equity else None,
        "current_holdings": holdings,
        "days_tracked": len(daily_points),
        "history": daily_points,
        "note": (
            "Portefeuille SIMULÉ (paper trading Alpaca, aucun argent réel). "
            "Positions flexibles : achetées dans le top PAPER_TRADING_TOP_N du score "
            "du matin, revendues automatiquement au-delà de "
            "PAPER_TRADING_TAKE_PROFIT_PCT de gain ou PAPER_TRADING_STOP_LOSS_PCT de "
            "perte — peuvent être tenues plusieurs jours entre ces deux seuils."
        ),
    }
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def run_paper_trading():
    client = get_client()
    if client is None:
        return

    clock = client.get_clock()
    if not clock.is_open:
        print(f"[paper_trade] Marché fermé actuellement (prochain jour de bourse : {clock.next_open}) — bot ignoré.")
        return

    today = today_str()
    snapshot = find_morning_snapshot(today)
    if snapshot is None:
        print(f"[paper_trade] Aucun run de nuit trouvé pour aujourd'hui ({today}) — bot ignoré.")
        return

    account = client.get_account()
    equity_at_open = float(account.equity)
    print(f"[paper_trade] Équité du compte paper à l'ouverture : {equity_at_open:.2f} $")

    held_tickers = {p.symbol for p in client.get_all_positions()}
    free_slots = PAPER_TRADING_TOP_N - len(held_tickers)
    print(f"[paper_trade] {len(held_tickers)} position(s) déjà tenue(s) (report des jours précédents), "
          f"{max(free_slots, 0)} place(s) libre(s) sur {PAPER_TRADING_TOP_N}.")

    day_record = load_day_record(today)
    day_record["equity_at_open"] = equity_at_open

    if free_slots <= 0:
        print("[paper_trade] Aucune place libre — pas de nouvel achat aujourd'hui.")
        save_day_record(day_record)
        rebuild_summary(client)
        return

    candidates = [row["ticker"] for row in snapshot["watchlist"] if row["ticker"] not in held_tickers]
    new_tickers = candidates[:free_slots]

    if not new_tickers:
        print("[paper_trade] Aucun nouveau candidat (tous les tickers du top sont déjà tenus) — rien à acheter.")
        save_day_record(day_record)
        rebuild_summary(client)
        return

    print(f"[paper_trade] Nouveaux candidats à acheter ({len(new_tickers)}, score du matin) : {new_tickers}")

    buying_power = float(account.buying_power)
    # Marge de sécurité : le prix peut légèrement bouger entre la lecture du
    # buying power et l'exécution de l'ordre suivant, un ordre à 100% pile
    # du buying power peut être rejeté pour quelques centimes.
    allocation_per_ticker = (buying_power * 0.98) / len(new_tickers)

    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    for ticker in new_tickers:
        entry = {"ticker": ticker, "notional": round(allocation_per_ticker, 2)}
        try:
            order_req = MarketOrderRequest(
                symbol=ticker,
                notional=round(allocation_per_ticker, 2),
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )
            order = client.submit_order(order_req)
            entry["order_id"] = str(order.id)
            entry["status"] = str(order.status)
            print(f"[paper_trade] Ordre soumis : {ticker} pour {allocation_per_ticker:.2f} $")
        except Exception as e:
            entry["error"] = str(e)
            print(f"[paper_trade] {ticker} : échec de l'ordre ({e})")
        day_record["entries"].append(entry)
        time.sleep(0.3)

    save_day_record(day_record)
    print(f"[paper_trade] Journal du jour mis à jour : {os.path.join(PAPER_TRADES_DIR, today + '.json')}")

    _prune_paper_trades_log()
    summary = rebuild_summary(client)
    print(f"[paper_trade] Équité : {equity_at_open:.2f} $ -> {summary['current_equity']:.2f} $ "
          f"(cumulé depuis le début : {summary['total_return_pct']}%)")


if __name__ == "__main__":
    run_paper_trading()
