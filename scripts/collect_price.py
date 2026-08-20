"""
Collecte prix et volume via Yahoo Finance (`yfinance`, gratuit, sans clé
API). C'est un accès non officiel à l'API interne de Yahoo Finance, très
largement utilisé par la communauté de projets perso — mais Yahoo peut
changer son backend sans préavis, comme StockTwits. Si ce script casse,
c'est le deuxième endroit à vérifier après collect_stocktwits.py.

Pourquoi ce signal : un score d'attention élevé (sentiment + news) combiné
à un volume d'échange anormalement haut est un bien meilleur indicateur
qu'un score de sentiment seul — ça distingue un vrai mouvement de marché
d'un pic de bruit social sans rien derrière.

Signal retenu : ratio volume du jour / volume moyen sur la période de
lookback, avec un bonus si la variation de prix est elle-même forte (dans
un sens ou dans l'autre — c'est un signal d'attention, pas un signal
directionnel achat/vente, cf. scoring.py).
"""
import yfinance as yf

from config import PRICE_VOLUME_LOOKBACK_DAYS, WATCHLIST


def collect_all_prices(watchlist=None):
    """Télécharge prix et volume pour toute la watchlist en un seul appel
    groupé (plus efficace qu'un appel par ticker).

    Renvoie {ticker: {"price": float, "change_pct": float, "volume": int,
    "avg_volume": float, "volume_ratio": float}}. Un ticker manquant (échec
    de récupération, delisting...) est simplement absent — le pipeline ne
    plante pas."""
    watchlist = watchlist or WATCHLIST
    results = {}

    try:
        data = yf.download(
            tickers=" ".join(watchlist),
            period=f"{PRICE_VOLUME_LOOKBACK_DAYS}d",
            interval="1d",
            group_by="ticker",
            progress=False,
            threads=True,
            auto_adjust=True,
        )
    except Exception as e:
        print(f"[collect_price] Erreur de téléchargement groupé : {e}")
        return results

    for ticker in watchlist:
        try:
            df = data[ticker] if len(watchlist) > 1 else data
            closes = df["Close"].dropna()
            volumes = df["Volume"].dropna()
            if len(closes) < 2 or len(volumes) < 2:
                continue

            last_close = float(closes.iloc[-1])
            prev_close = float(closes.iloc[-2])
            change_pct = ((last_close - prev_close) / prev_close) * 100 if prev_close else 0.0

            last_volume = float(volumes.iloc[-1])
            avg_volume = float(volumes.iloc[:-1].mean()) if len(volumes) > 1 else last_volume
            volume_ratio = (last_volume / avg_volume) if avg_volume else 1.0

            results[ticker] = {
                "ticker": ticker,
                "price": round(last_close, 2),
                "change_pct": round(change_pct, 2),
                "volume": int(last_volume),
                "avg_volume": round(avg_volume, 0),
                "volume_ratio": round(volume_ratio, 2),
            }
        except Exception as e:
            print(f"[collect_price] {ticker} : erreur ({e})")
            continue

    return results


if __name__ == "__main__":
    import json

    print(json.dumps(collect_all_prices(), indent=2))
