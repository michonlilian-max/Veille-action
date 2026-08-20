"""
Mouvements des initiés (Form 4) et des grands investisseurs (13F-HR) via
SEC EDGAR — gratuit, aucune clé API requise.

La SEC exige un User-Agent identifiable sur toutes les requêtes
(nom + email), sinon elle bloque l'IP. Configure SEC_USER_AGENT dans
config.py avec tes propres informations avant de lancer ce script.

Fonctionnement :
1. On résout le CIK (identifiant SEC) de chaque ticker via le fichier
   officiel company_tickers.json.
2. Pour les Form 4, on consulte l'historique de dépôts de la société elle-
   même (submissions API) et on filtre les Form 4 récents — un Form 4 est
   déposé sous le CIK de l'émetteur, donc cette source est fiable et
   directement liée au ticker.
3. Pour les 13F-HR, on effectue une recherche plein texte EDGAR sur le nom
   de la société : un 13F-HR est déposé par le *fonds* qui détient des
   positions, pas par la société elle-même, donc il n'apparaît jamais dans
   les dépôts propres de l'émetteur. La recherche plein texte est donc une
   approximation "best effort" (peut rater ou sur-compter des mentions).

Limite connue (cf. README, "Prochaines améliorations") : on compte ici
uniquement le nombre de dépôts récents, pas le détail achat/vente. Ce
détail demanderait de parser le XML de chaque Form 4 individuel.
"""
import time
from datetime import datetime, timedelta, timezone

import requests

from config import (
    FILING_13F_LOOKBACK_DAYS,
    INSIDER_LOOKBACK_DAYS,
    REQUEST_TIMEOUT,
    SEC_USER_AGENT,
    WATCHLIST,
)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FULL_TEXT_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"

HEADERS = {"User-Agent": SEC_USER_AGENT}

_company_cache = None


def _load_company_table():
    """Télécharge et met en cache la table officielle ticker -> CIK/nom."""
    global _company_cache
    if _company_cache is not None:
        return _company_cache
    try:
        resp = requests.get(TICKERS_URL, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"  [edgar] impossible de charger company_tickers.json ({e})")
        _company_cache = {}
        return _company_cache

    _company_cache = {
        entry["ticker"].upper(): {"cik": entry["cik_str"], "title": entry.get("title", "")}
        for entry in data.values()
    }
    return _company_cache


def _get_company(ticker):
    return _load_company_table().get(ticker.upper())


def _recent_filings_for_company(cik, form_prefix, lookback_days):
    """Renvoie les dépôts récents d'un type donné pour une société, en
    consultant l'historique complet de ses propres dépôts."""
    url = SUBMISSIONS_URL.format(cik=cik)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"  [edgar] CIK {cik}: erreur ({e})")
        return []

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accession_numbers = recent.get("accessionNumber", [])

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    filings = []
    for form, date_str, accn in zip(forms, dates, accession_numbers):
        if not form.startswith(form_prefix):
            continue
        try:
            filing_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if filing_date < cutoff:
            continue
        filings.append({"form": form, "filing_date": date_str, "accession_number": accn})
    return filings


def collect_insider_trades(watchlist=None):
    """Form 4 récents (achats/ventes de dirigeants), par ticker."""
    watchlist = watchlist or WATCHLIST
    results = []
    for ticker in watchlist:
        company = _get_company(ticker)
        if company is None:
            print(f"  [edgar] {ticker}: CIK introuvable, ignoré")
            continue
        filings = _recent_filings_for_company(company["cik"], "4", INSIDER_LOOKBACK_DAYS)
        for f in filings:
            results.append({"ticker": ticker, **f})
        time.sleep(0.2)  # reste raisonnable vis-à-vis de la SEC
    return results


def _recent_13f_mentions(company_title, lookback_days):
    """Recherche plein texte EDGAR des 13F-HR récents mentionnant le nom de
    la société. Best effort : cf. docstring du module."""
    if not company_title:
        return []
    start = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    params = {
        "q": f'"{company_title}"',
        "forms": "13F-HR",
        "dateRange": "custom",
        "startdt": start,
        "enddt": end,
    }
    try:
        resp = requests.get(
            FULL_TEXT_SEARCH_URL, headers=HEADERS, params=params, timeout=REQUEST_TIMEOUT
        )
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        print(f"  [edgar] 13F recherche '{company_title}': erreur ({e})")
        return []

    hits = (data.get("hits") or {}).get("hits") or []
    filings = []
    for hit in hits:
        source = hit.get("_source", {})
        filings.append(
            {
                "form": source.get("forms", ["13F-HR"])[0] if source.get("forms") else "13F-HR",
                "filing_date": source.get("file_date", ""),
                "filer": ", ".join(source.get("display_names", [])),
            }
        )
    return filings


def collect_13f_filings(watchlist=None):
    """13F-HR récents mentionnant une société de la watchlist, par ticker."""
    watchlist = watchlist or WATCHLIST
    results = []
    for ticker in watchlist:
        company = _get_company(ticker)
        if company is None:
            continue
        filings = _recent_13f_mentions(company["title"], FILING_13F_LOOKBACK_DAYS)
        for f in filings:
            results.append({"ticker": ticker, **f})
        time.sleep(0.2)
    return results


if __name__ == "__main__":
    import json

    print(
        json.dumps(
            {"insider": collect_insider_trades(), "13f": collect_13f_filings()},
            indent=2,
        )
    )
