"""
Mouvements des initiés (Form 4) et des grands investisseurs (13F-HR) via
SEC EDGAR — gratuit, aucune clé API requise.

SEC EDGAR exige un User-Agent identifiable (nom + email) sur chaque
requête, sous peine de blocage temporaire de l'IP. Voir config.SEC_USER_AGENT.

Historique : la première version interrogeait le flux "getcurrent" (les 40
derniers dépôts, tous marchés confondus) puis cherchait le ticker en texte
libre dans le titre. Deux problèmes la rendaient inutilisable en pratique :
1. Les 40 derniers dépôts du marché entier ont très peu de chances de
   contenir un des tickers suivis.
2. Les titres SEC affichent le nom légal de la société ("APPLE INC"),
   jamais le ticker ("AAPL") — donc même un dépôt pertinent ne matchait
   presque jamais.

Cette version résout le CIK (identifiant SEC) de chaque ticker une fois via
le fichier officiel company_tickers.json, puis :
- Form 4 : consulte l'historique de dépôts propre à chaque société
  (submissions API) — fiable, un Form 4 est déposé sous le CIK de
  l'émetteur.
- 13F-HR : un 13F-HR est déposé par le FONDS qui détient des actions,
  jamais par la société elle-même, donc impossible à trouver dans
  l'historique propre d'un émetteur. On utilise la recherche plein texte
  EDGAR sur le nom de la société — best-effort (le nom d'un émetteur dans
  la table de positions d'un 13F peut différer légèrement du nom légal
  complet, donc ça peut sous-compter).

Chaque Form 4 est en plus classé achat / vente / autre (champ
"transaction_type") en téléchargeant et parsant son XML individuel :
le code "P" (achat en marché ouvert) ou "S" (vente en marché ouvert) est
lu dans <transactionCoding><transactionCode>. Les attributions gratuites,
exercices d'options et retenues fiscales ("A", "M", "F", "G"...) sont
classées "other" — ce ne sont pas de vrais signaux d'achat/vente
volontaire. Le score ne retient ensuite que les vrais achats (cf.
scoring.py), ce qui corrige un mislabeling : la colonne s'appelle
"insider_buying" mais comptait avant tout Form 4 confondu, ventes
comprises.
"""
import time
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

import requests

from config import (
    FILING_13F_LOOKBACK_DAYS,
    INSIDER_LOOKBACK_DAYS,
    SEC_USER_AGENT,
    WATCHLIST,
)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
FULL_TEXT_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
FILING_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accn_nodash}/{doc}"

HEADERS = {"User-Agent": SEC_USER_AGENT}

# Codes de transaction SEC qui comptent comme un vrai achat/vente
# volontaire en marché ouvert (cf. formulaire officiel Form 4, case 3) :
BUY_CODES = {"P"}
SELL_CODES = {"S"}

_company_cache = None


def _load_company_table():
    """Télécharge et met en cache la table officielle ticker -> CIK/nom."""
    global _company_cache
    if _company_cache is not None:
        return _company_cache
    try:
        resp = requests.get(TICKERS_URL, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        _company_cache = {
            entry["ticker"].upper(): {"cik": entry["cik_str"], "title": entry.get("title", "")}
            for entry in data.values()
        }
    except Exception as e:
        print(f"[collect_edgar] Impossible de charger company_tickers.json : {e}")
        _company_cache = {}
    return _company_cache


def _get_company(ticker):
    return _load_company_table().get(ticker.upper())


def _local_name(tag):
    """Nom de balise sans préfixe d'espace de noms XML (ex:
    '{http://.../ns}transactionCode' -> 'transactionCode'). Les documents
    XML Form 4 n'en déclarent normalement pas, mais mieux vaut ne pas
    dépendre de l'absence de namespace pour un match de balise."""
    return tag.split("}")[-1] if "}" in tag else tag


def _classify_transaction(cik, accession_number, primary_document):
    """Télécharge le XML d'un Form 4 individuel et détermine s'il contient
    un achat ("buy", code P) ou une vente ("sell", code S) en marché
    ouvert. "other" pour tout le reste (attributions, options, impôts...)
    ou si le document n'a pas pu être récupéré/parsé (avec log de
    l'erreur, pour distinguer un vrai échec réseau/parsing d'un filing qui
    ne contient légitimement aucun code P/S).

    Le champ "primaryDocument" de submissions.json référence parfois le
    document sous un sous-dossier "xslF345X06/" — c'est la version HTML
    rendue par la SEC pour affichage navigateur (XSLT appliqué), pas le
    XML brut, même si le nom de fichier finit en .xml. Le vrai XML existe
    à la racine du dossier de dépôt sous le même nom de fichier — on ne
    garde donc que le nom de fichier, sans le sous-dossier.
    """
    if not primary_document:
        return "other"
    accn_nodash = accession_number.replace("-", "")
    doc_filename = primary_document.rsplit("/", 1)[-1]
    url = FILING_DOC_URL.format(cik=cik, accn_nodash=accn_nodash, doc=doc_filename)
    resp = None
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception as e:
        # Si resp existe, on logue le tout début du corps de la réponse :
        # une erreur de parsing identique (même ligne/colonne) sur des
        # dizaines de filings différents sent la page d'erreur générique
        # (limite de débit SEC) plutôt qu'un vrai XML mal formé filing par
        # filing — cet extrait permet de confirmer sans deviner.
        snippet = resp.text[:200].replace("\n", " ") if resp is not None else "(pas de réponse HTTP)"
        print(f"[collect_edgar] Form 4 XML {url} : erreur ({e}) — début réponse : {snippet!r}")
        return "other"

    # Recherche par nom local (sans namespace), et pas par chemin
    # nonDerivativeTransaction/transactionCoding/transactionCode : un find()
    # par chemin échoue silencieusement (aucune exception) si la structure
    # ou un namespace diffère de ce qu'on suppose, ce qui masquerait un vrai
    # bug de parsing derrière un innocent "other".
    codes = {
        el.text.strip()
        for el in root.iter()
        if _local_name(el.tag) == "transactionCode" and el.text
    }

    if codes & BUY_CODES:
        return "buy"
    if codes & SELL_CODES:
        return "sell"
    return "other"


def collect_insider_trades(watchlist=None):
    """Form 4 récents (achats/ventes de dirigeants), résolus par CIK, avec
    classification achat/vente réelle sur chaque dépôt.

    Renvoie une liste à plat de dicts, chacun déjà attribué à son ticker
    (champ "ticker") et à un type de transaction (champ "transaction_type" :
    "buy", "sell" ou "other") — pas besoin de re-matcher du texte côté
    scoring.
    """
    watchlist = watchlist or WATCHLIST
    cutoff = datetime.now(timezone.utc) - timedelta(days=INSIDER_LOOKBACK_DAYS)
    results = []

    for ticker in watchlist:
        company = _get_company(ticker)
        if company is None:
            print(f"[collect_edgar] {ticker} : CIK introuvable, ignoré")
            continue

        url = SUBMISSIONS_URL.format(cik=company["cik"])
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"[collect_edgar] {ticker} (CIK {company['cik']}) : erreur ({e})")
            time.sleep(0.2)
            continue

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accession_numbers = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])

        for form, date_str, accn, primary_doc in zip(forms, dates, accession_numbers, primary_docs):
            if form not in ("4", "4/A"):
                continue
            try:
                filing_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                continue
            if filing_date < cutoff:
                continue

            transaction_type = _classify_transaction(company["cik"], accn, primary_doc)
            time.sleep(0.4)  # un fetch par filing individuel — plus espacé pour rester large

            results.append(
                {
                    "ticker": ticker,
                    "title": f"Form 4 — {company['title']}",
                    "form": form,
                    "filing_date": date_str,
                    "accession_number": accn,
                    "transaction_type": transaction_type,
                }
            )
        time.sleep(0.2)  # reste raisonnable vis-à-vis de la SEC

    return results


def _recent_13f_mentions(ticker, company_title, lookback_days):
    """Recherche plein texte EDGAR des 13F-HR récents mentionnant le nom
    de la société. Best effort — cf. docstring du module."""
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
        resp = requests.get(FULL_TEXT_SEARCH_URL, headers=HEADERS, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[collect_edgar] 13F '{company_title}' : erreur ({e})")
        return []

    hits = (data.get("hits") or {}).get("hits") or []
    results = []
    for hit in hits:
        source = hit.get("_source", {})
        filer_names = ", ".join(source.get("display_names", []))
        results.append(
            {
                "ticker": ticker,
                "title": f"13F-HR — {filer_names}",
                "filing_date": source.get("file_date", ""),
            }
        )
    return results


def collect_13f_filings(watchlist=None):
    """13F-HR récents mentionnant une société de la watchlist, par ticker.

    Renvoie une liste à plat de dicts, chacun déjà attribué à son ticker.
    """
    watchlist = watchlist or WATCHLIST
    results = []
    for ticker in watchlist:
        company = _get_company(ticker)
        if company is None:
            continue
        results.extend(_recent_13f_mentions(ticker, company["title"], FILING_13F_LOOKBACK_DAYS))
        time.sleep(0.3)
    return results


if __name__ == "__main__":
    import json

    print(
        json.dumps(
            {"insider": collect_insider_trades(), "13f": collect_13f_filings()},
            indent=2,
        )
    )
