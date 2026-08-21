"""
Clôture quotidienne du bot de paper trading (cf. scripts/paper_trade.py
pour le contexte général et l'avertissement de sécurité sur paper=True).

Exécuté en fin de séance (cf. .github/workflows/close_paper_trades.yml) :
revend toutes les positions ouvertes ce matin, calcule la performance
réelle de la journée, complète le journal du jour et envoie un email
récapitulatif. Aucune position n'est jamais gardée la nuit — le bot
recommence de zéro chaque jour de bourse.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.paper_trade import PAPER_TRADES_DIR, get_client, rebuild_summary
from scripts.send_email import send_paper_trade_report


def close_paper_trading():
    client = get_client()
    if client is None:
        return

    clock = client.get_clock()
    if not clock.is_open:
        print(f"[close_paper_trades] Marché déjà fermé (prochaine ouverture : {clock.next_open}) — clôture ignorée.")
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    day_path = os.path.join(PAPER_TRADES_DIR, f"{today}.json")
    if not os.path.exists(day_path):
        print(f"[close_paper_trades] Aucun journal d'ouverture trouvé pour aujourd'hui ({today}) — "
              "le bot n'a probablement pas acheté ce matin. Clôture ignorée.")
        return

    with open(day_path, encoding="utf-8") as f:
        day_record = json.load(f)

    positions = client.get_all_positions()
    if not positions:
        print("[close_paper_trades] Aucune position ouverte à revendre.")
        positions_snapshot = []
    else:
        positions_snapshot = [
            {"ticker": p.symbol, "qty": p.qty, "market_value": float(p.market_value)}
            for p in positions
        ]

    account_before_close = client.get_account()
    equity_before_close = float(account_before_close.equity)
    print(f"[close_paper_trades] Équité juste avant clôture : {equity_before_close:.2f} $")

    if positions:
        print(f"[close_paper_trades] Revente de {len(positions_snapshot)} position(s)...")
        client.close_all_positions(cancel_orders=True)
        time.sleep(5)  # laisser les ordres de vente se remplir

    account_after_close = client.get_account()
    equity_after_close = float(account_after_close.equity)

    equity_after_open = day_record.get("equity_after")
    intraday_return_pct = (
        round(100 * (equity_before_close - equity_after_open) / equity_after_open, 2)
        if equity_after_open else None
    )

    day_record["positions_closed"] = positions_snapshot
    day_record["equity_before_close"] = equity_before_close
    day_record["equity_after_close"] = equity_after_close
    day_record["intraday_return_pct"] = intraday_return_pct

    with open(day_path, "w", encoding="utf-8") as f:
        json.dump(day_record, f, ensure_ascii=False, indent=2)
    print(f"[close_paper_trades] Journal du jour complété : {day_path}")

    summary = rebuild_summary(current_equity=equity_after_close, current_holdings=[])

    sign = "+" if (intraday_return_pct or 0) >= 0 else ""
    print(f"[close_paper_trades] Performance du jour : {sign}{intraday_return_pct}% "
          f"(équité : {equity_after_open:.2f} $ -> {equity_before_close:.2f} $ avant clôture, "
          f"{equity_after_close:.2f} $ après revente)")

    send_paper_trade_report(day_record, summary)


if __name__ == "__main__":
    close_paper_trading()
