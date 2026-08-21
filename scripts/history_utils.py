"""
Petit utilitaire partagé entre scripts/backtest.py et scripts/paper_trade.py :
retrouver l'instantané data/history/ généré par le run de nuit d'aujourd'hui.
Les deux scripts tournent l'après-midi/en journée et ont besoin du même
point de référence ("le score calculé ce matin"), donc autant centraliser
cette logique plutôt que de la dupliquer.
"""
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_DIR = os.path.join(ROOT, "data", "history")


def find_morning_snapshot(today: str) -> dict | None:
    """Retrouve l'instantané data/history/ généré ce matin (avant midi UTC —
    le run de nuit tourne à 03h00 UTC, ~3h à l'échelle S&P 500, donc
    termine largement avant midi). Renvoie None si aucun run n'a eu lieu
    aujourd'hui avant midi (ex: jour férié US, run de nuit en échec)."""
    candidates = sorted(glob.glob(os.path.join(HISTORY_DIR, f"{today}T*.json")))
    for path in candidates:
        hour = os.path.basename(path)[11:13]  # "2026-08-21T03.json" -> "03"
        try:
            if int(hour) < 12:
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
        except ValueError:
            continue
    return None
