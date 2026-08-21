"""
Candidats du S&P MidCap 400 à une future inclusion au S&P 500.

Idée : quand une société rejoint le S&P 500, les fonds indiciels qui
répliquent l'indice sont mécaniquement obligés d'en acheter — un effet
d'inclusion documenté en finance de marché. Ce module cherche, parmi les
~400 sociétés du MidCap 400, celles qui ressemblent le plus à de bonnes
candidates à une inclusion prochaine.

⚠️ Ce n'est jamais une prédiction certaine :
- L'inclusion est décidée par un comité (S&P Dow Jones Indices) qui
  regarde aussi l'équilibre sectoriel et la liquidité, pas seulement la
  capitalisation — cf. le disclaimer inclus dans data/midcap_candidates.json.
- Le filtre de rentabilité utilise le BPA 12 mois glissants, une
  approximation du vrai critère S&P (bénéfice GAAP positif sur les 4
  derniers trimestres ET le dernier trimestre) — cf. collect_market_cap.py.
- L'annonce officielle n'arrive en général que quelques jours avant
  l'effet réel — même bien fait, ceci reste un "candidat plausible", pas
  une avance de plusieurs mois.

Méthode :
1. Capitalisation boursière du S&P 500 actuel ET du MidCap 400 (yfinance,
   un appel par ticker — lent, ~900 tickers au total, cf. le workflow
   dédié qui tourne une fois par semaine plutôt que chaque nuit)
2. "Plancher" S&P 500 = moyenne des SP500_FLOOR_SAMPLE_SIZE plus petites
   capitalisations actuelles de l'indice
3. Filtre : exclut tout candidat MidCap 400 dont le BPA 12 mois n'est
   pas positif (pas éligible, peu importe sa taille)
4. Score de proximité = capitalisation du candidat / plancher S&P 500 —
   dominant dans le score final (cf. MIDCAP_WEIGHTS), complété par les
   signaux d'attention déjà utilisés dans le pipeline principal (news,
   achats d'initiés, volume) sur les meilleurs candidats préliminaires
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import MIDCAP_TOP_N, MIDCAP_WEIGHTS, SP500_FLOOR_SAMPLE_SIZE
from scripts.collect_edgar import collect_insider_trades
from scripts.collect_market_cap import collect_market_cap_data
from scripts.collect_news import collect_news_for_ticker
from scripts.collect_price import collect_all_prices
from scripts.fetch_midcap400 import fetch_midcap400_tickers
from scripts.fetch_sp500 import fetch_sp500_tickers
from scripts.scoring import _normalize
from scripts.send_email import send_midcap_report

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(ROOT, "data", "midcap_candidates.json")

# Nombre de candidats préliminaires (triés par proximité de capitalisation
# seule) sur lesquels on lance les collectes plus coûteuses (news,
# insiders, volume) — pas la peine de les faire tourner sur les ~400.
PRELIM_POOL_SIZE = 60


def run_midcap_candidates():
    print("Récupération des univers S&P 500 et S&P MidCap 400...")
    sp500 = fetch_sp500_tickers()
    midcap = fetch_midcap400_tickers()
    if not sp500 or not midcap:
        print("Impossible d'obtenir les deux univers (S&P 500 et/ou MidCap 400) — abandon.")
        return
    print(f"{len(sp500)} tickers S&P 500, {len(midcap)} tickers MidCap 400.")

    print(f"Capitalisation boursière + BPA pour {len(sp500) + len(midcap)} tickers "
          "(un appel par ticker, ça prend plusieurs minutes)...")
    sp500_caps = collect_market_cap_data(sp500)
    midcap_caps = collect_market_cap_data(midcap)

    sp500_market_caps = sorted(
        v["market_cap"] for v in sp500_caps.values() if v.get("market_cap")
    )
    if len(sp500_market_caps) < SP500_FLOOR_SAMPLE_SIZE:
        print(f"Seulement {len(sp500_market_caps)} capitalisations S&P 500 récupérées "
              f"(besoin d'au moins {SP500_FLOOR_SAMPLE_SIZE}) — plancher non fiable, abandon.")
        return
    floor_value = sum(sp500_market_caps[:SP500_FLOOR_SAMPLE_SIZE]) / SP500_FLOOR_SAMPLE_SIZE
    print(f"Plancher S&P 500 (moyenne des {SP500_FLOOR_SAMPLE_SIZE} plus petites "
          f"capitalisations actuelles) : {floor_value / 1e9:.1f} Md$")

    eligible = [
        t for t in midcap
        if midcap_caps.get(t, {}).get("trailing_eps") is not None
        and midcap_caps[t]["trailing_eps"] > 0
        and midcap_caps[t].get("market_cap")
    ]
    print(f"{len(eligible)}/{len(midcap)} candidats passent le filtre de rentabilité "
          "(BPA 12 mois glissants positif).")
    if not eligible:
        print("Aucun candidat éligible — abandon.")
        return

    proximity_raw = {t: midcap_caps[t]["market_cap"] / floor_value for t in eligible}
    prelim = sorted(eligible, key=lambda t: proximity_raw[t], reverse=True)[:PRELIM_POOL_SIZE]

    print(f"Collecte news/initiés/volume sur les {len(prelim)} candidats préliminaires "
          "(les plus proches du plancher S&P 500)...")
    news_data = {t: collect_news_for_ticker(t) for t in prelim}
    insider_filings = collect_insider_trades(watchlist=prelim)
    price_data = collect_all_prices(watchlist=prelim)

    news_raw = {t: len(news_data.get(t, [])) for t in prelim}

    insider_raw = {t: 0 for t in prelim}
    for filing in insider_filings:
        t = filing.get("ticker")
        if t in insider_raw and filing.get("transaction_type") == "buy":
            insider_raw[t] += 1

    volume_raw = {}
    for t in prelim:
        p = price_data.get(t)
        if p:
            volume_raw[t] = p.get("volume_ratio", 1.0) * (1 + min(abs(p.get("change_pct", 0.0)), 20) / 20)
        else:
            volume_raw[t] = 0.0

    prox_n = _normalize({t: proximity_raw[t] for t in prelim})
    news_n = _normalize(news_raw)
    insider_n = _normalize(insider_raw)
    volume_n = _normalize(volume_raw)

    results = []
    for t in prelim:
        score = (
            MIDCAP_WEIGHTS["cap_proximity"] * prox_n.get(t, 0)
            + MIDCAP_WEIGHTS["news_volume"] * news_n.get(t, 0)
            + MIDCAP_WEIGHTS["insider_buying"] * insider_n.get(t, 0)
            + MIDCAP_WEIGHTS["volume_spike"] * volume_n.get(t, 0)
        )
        p = price_data.get(t) or {}
        results.append({
            "ticker": t,
            "score": round(score, 1),
            "market_cap": round(midcap_caps[t]["market_cap"], 0),
            "market_cap_vs_sp500_floor_pct": round(100 * proximity_raw[t], 1),
            "trailing_eps": midcap_caps[t]["trailing_eps"],
            "news_count": news_raw.get(t, 0),
            "insider_buys": insider_raw.get(t, 0),
            "price": p.get("price"),
            "change_pct": p.get("change_pct"),
            "volume_ratio": p.get("volume_ratio"),
            "detail": {
                "cap_proximity": prox_n.get(t, 0),
                "news_volume": news_n.get(t, 0),
                "insider_buying": insider_n.get(t, 0),
                "volume_spike": volume_n.get(t, 0),
            },
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    top = results[:MIDCAP_TOP_N]

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sp500_floor_market_cap": round(floor_value, 0),
        "sp500_floor_sample_size": SP500_FLOOR_SAMPLE_SIZE,
        "eligible_count": len(eligible),
        "total_midcap_count": len(midcap),
        "candidates": top,
        "disclaimer": (
            "Estimation, pas une prédiction. L'inclusion au S&P 500 est décidée par un "
            "comité (S&P Dow Jones Indices) qui considère aussi l'équilibre sectoriel et la "
            "liquidité, pas seulement la capitalisation. Le filtre de rentabilité utilise le "
            "BPA sur 12 mois glissants (approximation du vrai critère S&P : bénéfice GAAP "
            "positif sur les 4 derniers trimestres ET le dernier trimestre). L'annonce "
            "officielle d'une inclusion n'arrive en général que quelques jours avant l'effet "
            "réel — ceci reste un candidat plausible, pas une prédiction à long terme."
        ),
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"Terminé. Top {len(top)} candidats écrits dans {OUTPUT_PATH}")
    print("Top 5 :")
    for r in top[:5]:
        print(f"  {r['ticker']}: score {r['score']}, cap {r['market_cap'] / 1e9:.1f} Md$ "
              f"({r['market_cap_vs_sp500_floor_pct']}% du plancher S&P 500)")

    print("Envoi de l'email récapitulatif (si configuré)...")
    send_midcap_report(output)


if __name__ == "__main__":
    run_midcap_candidates()
