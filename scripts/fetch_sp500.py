"""
Récupère la liste des sociétés du S&P 500 (~500 tickers) à chaque run,
depuis un jeu de données communautaire mis à jour régulièrement, hébergé
sur GitHub (pas de clé API, pas de scraping fragile de page HTML) :
https://github.com/datasets/s-and-p-500-companies

Pourquoi dynamique plutôt qu'une liste figée dans config.py : le S&P 500
est recomposé plusieurs fois par an (sociétés qui entrent/sortent de
l'indice) — une liste statique de 500 tickers deviendrait obsolète en
quelques mois sans qu'on s'en aperçoive.

Si la récupération échoue (source indisponible, format changé, réponse
tronquée...), on renvoie [] plutôt que de deviner : c'est à l'appelant
(config.py) de retomber sur FALLBACK_WATCHLIST. Mieux vaut un univers
réduit mais garanti correct qu'un univers large et potentiellement faux.
"""
import sys

import requests

CONSTITUENTS_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/"
    "master/data/constituents.csv"
)

# Un CSV valide du S&P 500 contient ~500 lignes. En dessous de ce seuil,
# la réponse est probablement tronquée, vide ou une page d'erreur — on
# préfère refuser plutôt que de suivre un univers partiel sans le savoir.
MIN_EXPECTED_TICKERS = 400


def fetch_sp500_tickers() -> list[str]:
    """Renvoie la liste actuelle des tickers du S&P 500, ou [] en cas
    d'échec (réseau, format inattendu, réponse suspecte)."""
    try:
        resp = requests.get(CONSTITUENTS_URL, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"[fetch_sp500] Récupération impossible : {e}", file=sys.stderr)
        return []

    lines = resp.text.strip().splitlines()
    if not lines:
        print("[fetch_sp500] Réponse vide.", file=sys.stderr)
        return []

    header = lines[0].split(",")
    try:
        symbol_idx = header.index("Symbol")
    except ValueError:
        print(f"[fetch_sp500] Colonne 'Symbol' introuvable dans l'en-tête : {header}", file=sys.stderr)
        return []

    tickers = []
    for line in lines[1:]:
        if not line.strip():
            continue
        cols = line.split(",")
        if symbol_idx >= len(cols):
            continue
        symbol = cols[symbol_idx].strip().upper()
        if not symbol:
            continue
        # Tickers à classe d'actions (ex: BRK.B, BF.B) s'écrivent différemment
        # selon la source consultée (BRK.B / BRK-B / BRK B) — le pipeline
        # interroge 4 sources différentes (SEC, Yahoo, StockTwits, Google
        # News) sans garantie qu'elles partagent la même convention. Plutôt
        # que de deviner et risquer des échecs silencieux sur ces tickers-là
        # sur telle ou telle source, on les exclut (perte de 2-3 tickers sur
        # ~500, négligeable).
        if "." in symbol:
            continue
        tickers.append(symbol)

    if len(tickers) < MIN_EXPECTED_TICKERS:
        print(
            f"[fetch_sp500] Seulement {len(tickers)} tickers trouvés "
            f"(attendu ~500) — source suspecte, ignorée.",
            file=sys.stderr,
        )
        return []

    return tickers


if __name__ == "__main__":
    result = fetch_sp500_tickers()
    print(f"{len(result)} tickers récupérés.")
    print(result[:10], "...")
