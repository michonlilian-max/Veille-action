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

Stratégie — trading intrajournalier, aucune position gardée la nuit :
1. **À l'ouverture des marchés** (ce module, cf. .github/workflows/paper_trade.yml) :
   récupère le score calculé la nuit précédente, liquide toute position
   résiduelle (garde-fou, il ne devrait normalement plus y en avoir grâce
   au (2) ci-dessous), puis répartit la totalité du buying power à parts
   égales sur les PAPER_TRADING_TOP_N tickers les mieux classés.
2. **À la clôture des marchés** (cf. scripts/close_paper_trades.py) : revend
   tout, calcule la performance réelle de la journée, envoie un email
   récapitulatif et journalise le résultat.

Les deux scripts partagent le même fichier journalier dans
data/paper_trades/ (écrit le matin, complété le soir) et la même fonction
`rebuild_summary()` pour le résumé affiché sur le dashboard.
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
    partagé par paper_trade.py et close_paper_trades.py — paper=True
    câblé en dur ici aussi, voir l'avertissement de sécurité en tête de
    fichier."""
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


def rebuild_summary(current_equity, current_holdings):
    """Reconstruit data/paper_trades_summary.json à partir de tous les
    journaux quotidiens accumulés (data/paper_trades/*.json) — appelé par
    paper_trade.py (matin, après achat) ET close_paper_trades.py (soir,
    après clôture), donc `current_equity`/`current_holdings` reflètent
    l'état au moment de l'appel, pas forcément la fin de journée."""
    os.makedirs(PAPER_TRADES_DIR, exist_ok=True)
    summary_points = []
    for path in sorted(glob.glob(os.path.join(PAPER_TRADES_DIR, "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            summary_points.append({
                "date": d["date"],
                "equity_before": d.get("equity_before"),
                "equity_after_open": d.get("equity_after"),
                "equity_after_close": d.get("equity_after_close"),
                "intraday_return_pct": d.get("intraday_return_pct"),
            })
        except (json.JSONDecodeError, OSError, KeyError):
            continue

    starting_equity = summary_points[0]["equity_before"] if summary_points else current_equity
    summary = {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "starting_equity": starting_equity,
        "current_equity": current_equity,
        "total_return_pct": round(100 * (current_equity - starting_equity) / starting_equity, 2) if starting_equity else None,
        "current_holdings": current_holdings,
        "days_tracked": len(summary_points),
        "history": summary_points,
        "note": (
            "Portefeuille SIMULÉ (paper trading Alpaca, aucun argent réel). "
            "Trading intrajournalier : achat des PAPER_TRADING_TOP_N tickers par "
            "score du matin à l'ouverture, revente complète à la clôture — aucune "
            "position gardée la nuit."
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

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    snapshot = find_morning_snapshot(today)
    if snapshot is None:
        print(f"[paper_trade] Aucun run de nuit trouvé pour aujourd'hui ({today}) — bot ignoré.")
        return

    target_rows = snapshot["watchlist"][:PAPER_TRADING_TOP_N]
    target_tickers = [row["ticker"] for row in target_rows]
    print(f"[paper_trade] Cible du jour ({len(target_tickers)} tickers, score du matin) : {target_tickers}")

    account_before = client.get_account()
    equity_before = float(account_before.equity)
    print(f"[paper_trade] Équité du compte paper à l'ouverture : {equity_before:.2f} $")

    # Garde-fou : il ne devrait normalement plus y avoir de position à ce
    # stade (close_paper_trades.py a tout revendu la veille au soir), mais
    # on liquide quand même par sécurité (ex: script du soir en échec).
    positions_before = [
        {"ticker": p.symbol, "qty": p.qty, "market_value": float(p.market_value)}
        for p in client.get_all_positions()
    ]
    if positions_before:
        print(f"[paper_trade] {len(positions_before)} position(s) résiduelle(s) trouvée(s) (inattendu) — liquidation...")
        client.close_all_positions(cancel_orders=True)
        time.sleep(5)

    account_after_close = client.get_account()
    buying_power = float(account_after_close.buying_power)
    # Marge de sécurité : le prix peut légèrement bouger entre la lecture du
    # buying power et l'exécution de l'ordre suivant, un ordre à 100% pile
    # du buying power peut être rejeté pour quelques centimes.
    allocation_per_ticker = (buying_power * 0.98) / len(target_tickers) if target_tickers else 0

    orders = []
    for ticker in target_tickers:
        try:
            from alpaca.trading.requests import MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce
            order_req = MarketOrderRequest(
                symbol=ticker,
                notional=round(allocation_per_ticker, 2),
                side=OrderSide.BUY,
                time_in_force=TimeInForce.DAY,
            )
            order = client.submit_order(order_req)
            orders.append({
                "ticker": ticker,
                "notional": round(allocation_per_ticker, 2),
                "order_id": str(order.id),
                "status": str(order.status),
            })
            print(f"[paper_trade] Ordre soumis : {ticker} pour {allocation_per_ticker:.2f} $")
        except Exception as e:
            print(f"[paper_trade] {ticker} : échec de l'ordre ({e})")
            orders.append({"ticker": ticker, "notional": round(allocation_per_ticker, 2), "error": str(e)})
        time.sleep(0.3)

    account_final = client.get_account()
    equity_after = float(account_final.equity)

    day_record = {
        "date": today,
        "reference_run": snapshot["generated_at"],
        "equity_before": equity_before,
        "equity_after": equity_after,
        "buying_power_used": buying_power,
        "positions_liquidated": positions_before,
        "target_tickers": target_tickers,
        "orders": orders,
    }

    os.makedirs(PAPER_TRADES_DIR, exist_ok=True)
    day_path = os.path.join(PAPER_TRADES_DIR, f"{today}.json")
    with open(day_path, "w", encoding="utf-8") as f:
        json.dump(day_record, f, ensure_ascii=False, indent=2)
    print(f"[paper_trade] Journal du jour écrit : {day_path}")

    _prune_paper_trades_log()
    summary = rebuild_summary(current_equity=equity_after, current_holdings=target_tickers)
    print(f"[paper_trade] Équité : {equity_before:.2f} $ -> {equity_after:.2f} $ "
          f"(cumulé depuis le début : {summary['total_return_pct']}%)")


if __name__ == "__main__":
    run_paper_trading()
