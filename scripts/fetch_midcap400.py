"""
Récupère la liste des sociétés du S&P MidCap 400 à chaque run.

Contrairement au S&P 500 (cf. fetch_sp500.py), il n'existe pas de CSV
communautaire équivalent, activement maintenu, pour le MidCap 400. Un
candidat a été identifié (erez-meoded/S-and-P-500-400-constituents-...)
puis écarté : son fichier snp400.csv n'a plus été mis à jour depuis
novembre 2017 (vérifié) — il contenait encore ABMD (Abiomed), racheté et
retiré de la bourse en 2022. Utiliser cette liste aurait fait tourner le
reste du pipeline sur un univers en grande partie obsolète sans le
signaler.

À la place, on scrape la page Wikipédia "List of S&P 400 companies",
éditée par la communauté et à jour en pratique. C'est plus fragile qu'un
CSV propre (structure HTML qui peut changer), donc le parsing est
défensif : on cherche la colonne par en-tête ("Symbol"/"Ticker"), pas par
position fixe, et parmi tous les tableaux "wikitable" de la page on garde
celui qui donne le plus de tickers valides (évite de tomber sur un petit
tableau annexe, ex: "changements récents"). Si le nombre de tickers
trouvés est trop bas, on renvoie [] plutôt que de deviner — c'est à
l'appelant de retomber sur une liste de repli.
"""
import sys

import requests

WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"
HEADERS = {"User-Agent": "Mozilla/5.0 (VeilleActions; contact via config.py SEC_USER_AGENT)"}

# L'indice vise ~400 sociétés — en dessous de ce seuil, la page est
# probablement cassée, tronquée, ou on a attrapé le mauvais tableau.
MIN_EXPECTED_TICKERS = 350


def fetch_midcap400_tickers() -> list[str]:
    try:
        resp = requests.get(WIKI_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"[fetch_midcap400] Récupération impossible : {e}", file=sys.stderr)
        return []

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("[fetch_midcap400] Le paquet 'beautifulsoup4' n'est pas installé (cf. requirements.txt).", file=sys.stderr)
        return []

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"[fetch_midcap400] Parsing HTML impossible : {e}", file=sys.stderr)
        return []

    best_tickers: list[str] = []
    for table in soup.find_all("table", {"class": "wikitable"}):
        rows = table.find_all("tr")
        if not rows:
            continue

        header_cells = rows[0].find_all(["th", "td"])
        headers = [c.get_text(strip=True).lower() for c in header_cells]
        symbol_idx = next(
            (i for i, h in enumerate(headers) if "symbol" in h or "ticker" in h),
            None,
        )
        if symbol_idx is None:
            continue

        tickers = []
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if symbol_idx >= len(cells):
                continue
            symbol = cells[symbol_idx].get_text(strip=True).upper()
            # cf. fetch_sp500.py : tickers à classe d'actions (BRK.B...)
            # exclus plutôt que de deviner leur écriture selon la source.
            if not symbol or "." in symbol or " " in symbol:
                continue
            tickers.append(symbol)

        if len(tickers) > len(best_tickers):
            best_tickers = tickers

    if len(best_tickers) < MIN_EXPECTED_TICKERS:
        print(
            f"[fetch_midcap400] Seulement {len(best_tickers)} tickers trouvés "
            f"(attendu ~400) — page suspecte, ignorée.",
            file=sys.stderr,
        )
        return []

    return best_tickers


if __name__ == "__main__":
    result = fetch_midcap400_tickers()
    print(f"{len(result)} tickers récupérés.")
    print(result[:10], "...")
