"""
Capitalisation boursière + rentabilité (best-effort) par ticker, via
yfinance — nécessaire pour le module MidCap 400 (proximité du plancher
S&P 500 + filtre d'éligibilité, cf. scripts/midcap_candidates.py).

Contrairement à collect_price.py (un seul appel groupé), la
capitalisation et les bénéfices ne sont pas inclus dans le téléchargement
en masse de yfinance — un appel individuel par ticker est nécessaire
(`Ticker(...).info`), donc plus lent. Sur ~900 tickers (S&P 500 +
MidCap 400 combinés), compter plusieurs minutes.

Filtre de rentabilité — approximation assumée : la vraie règle
d'éligibilité S&P 500 exige un bénéfice GAAP positif sur les 4 derniers
trimestres cumulés ET sur le dernier trimestre. Récupérer les résultats
trimestriels détaillés pour ~400+ sociétés serait beaucoup plus lourd ;
on approxime avec le BPA sur les 12 derniers mois glissants
("trailingEps") — positif ou non. Documenté comme approximation partout
où ce filtre est utilisé, pas présenté comme le vrai critère S&P.
"""
import sys
import time

import yfinance as yf


def collect_market_cap_data(tickers: list[str]) -> dict[str, dict]:
    """Renvoie {ticker: {"market_cap": float|None, "trailing_eps": float|None}}.
    Un ticker en échec est simplement absent — le pipeline ne plante pas."""
    results = {}
    for ticker in tickers:
        try:
            info = yf.Ticker(ticker).info
            market_cap = info.get("marketCap")
            trailing_eps = info.get("trailingEps")
            results[ticker] = {
                "market_cap": float(market_cap) if market_cap else None,
                "trailing_eps": float(trailing_eps) if trailing_eps is not None else None,
            }
        except Exception as e:
            print(f"[collect_market_cap] {ticker} : erreur ({e})", file=sys.stderr)
        time.sleep(0.15)
    return results


if __name__ == "__main__":
    import json

    print(json.dumps(collect_market_cap_data(["AAPL", "MSFT", "NVDA"]), indent=2))
