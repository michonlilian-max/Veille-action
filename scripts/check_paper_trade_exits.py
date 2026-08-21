"""
Vérification des seuils de sortie du bot de paper trading (cf.
scripts/paper_trade.py pour le contexte général et l'avertissement de
sécurité sur paper=True).

Exécuté plusieurs fois par jour de bourse (cf.
.github/workflows/check_paper_trade_exits.yml) : pour chaque position
ouverte, vend automatiquement dès que le gain latent dépasse
PAPER_TRADING_TAKE_PROFIT_PCT ou que la perte latente dépasse
PAPER_TRADING_STOP_LOSS_PCT (cf. config.py). Une position entre ces deux
seuils n'est jamais touchée — elle peut rester ouverte plusieurs jours.

Sur le dernier passage de la journée (variable d'environnement
SEND_DAILY_REPORT=true, positionnée uniquement par le workflow du soir),
envoie en plus l'email récapitulatif de la journée.
"""
import os
import sys
import time
from datetime import timezone, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PAPER_TRADING_STOP_LOSS_PCT, PAPER_TRADING_TAKE_PROFIT_PCT
from scripts.paper_trade import get_client, load_day_record, rebuild_summary, save_day_record, today_str
from scripts.send_email import send_paper_trade_report


def check_exits():
    client = get_client()
    if client is None:
        return

    clock = client.get_clock()
    if not clock.is_open:
        print(f"[check_exits] Marché fermé actuellement (prochain jour de bourse : {clock.next_open}) — vérification ignorée.")
        return

    today = today_str()
    day_record = load_day_record(today)

    positions = client.get_all_positions()
    if not positions:
        print("[check_exits] Aucune position ouverte à vérifier.")
    else:
        print(f"[check_exits] {len(positions)} position(s) à vérifier "
              f"(take-profit +{PAPER_TRADING_TAKE_PROFIT_PCT}%, stop-loss -{PAPER_TRADING_STOP_LOSS_PCT}%)...")

    for p in positions:
        plpc = float(p.unrealized_plpc) * 100  # ex: 0.083 -> 8.3
        reason = None
        if plpc >= PAPER_TRADING_TAKE_PROFIT_PCT:
            reason = "take_profit"
        elif plpc <= -PAPER_TRADING_STOP_LOSS_PCT:
            reason = "stop_loss"

        if reason is None:
            print(f"[check_exits] {p.symbol} : {plpc:+.2f}% — dans la fourchette, on garde.")
            continue

        try:
            order = client.close_position(p.symbol)
            day_record["exits"].append({
                "ticker": p.symbol,
                "reason": reason,
                "unrealized_plpc": round(plpc, 2),
                "market_value": round(float(p.market_value), 2),
                "order_id": str(order.id),
            })
            label = "take-profit" if reason == "take_profit" else "stop-loss"
            print(f"[check_exits] {p.symbol} : {label} déclenché à {plpc:+.2f}% — position fermée.")
        except Exception as e:
            print(f"[check_exits] {p.symbol} : échec de la fermeture ({e})")
        time.sleep(0.3)

    save_day_record(day_record)
    summary = rebuild_summary(client)

    if os.environ.get("SEND_DAILY_REPORT", "").lower() == "true":
        account = client.get_account()
        day_record["equity_at_close"] = float(account.equity)
        save_day_record(day_record)
        summary = rebuild_summary(client)
        print("[check_exits] Envoi de l'email récapitulatif du jour...")
        send_paper_trade_report(day_record, summary)


if __name__ == "__main__":
    check_exits()
