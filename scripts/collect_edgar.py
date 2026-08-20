"""
Collecte les dépôts SEC récents (gratuit, sans clé API) :
- Form 4 : transactions d'initiés (achats/ventes par dirigeants, administrateurs, gros actionnaires)
- 13F-HR : positions trimestrielles des grands investisseurs institutionnels

SEC EDGAR exige un User-Agent identifiable (nom + email) sur chaque requête,
sous peine de blocage temporaire de l'IP. Voir config.SEC_USER_AGENT.

Doc officielle : https://www.sec.gov/os/webmaster-faq#developers
"""
import sys
import os
import time
import xml.etree.ElementTree as ET
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import SEC_USER_AGENT, SEC_MAX_FILINGS

EDGAR_CURRENT_FEED = "https://www.sec.gov/cgi-bin/browse-edgar"
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}


def _fetch_current_filings(form_type: str, count: int = SEC_MAX_FILINGS) -> list[dict]:
    """Interroge le flux Atom 'getcurrent' d'EDGAR pour un type de formulaire donné."""
    params = {
        "action": "getcurrent",
        "type": form_type,
        "company": "",
        "dateb": "",
        "owner": "include",
        "count": str(count),
        "output": "atom",
    }
    headers = {"User-Agent": SEC_USER_AGENT}
    resp = requests.get(EDGAR_CURRENT_FEED, params=params, headers=headers, timeout=20)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    entries = []
    for entry in root.findall("a:entry", ATOM_NS):
        title = entry.findtext("a:title", default="", namespaces=ATOM_NS)
        link_el = entry.find("a:link", ATOM_NS)
        link = link_el.get("href") if link_el is not None else None
        updated = entry.findtext("a:updated", default="", namespaces=ATOM_NS)
        summary = entry.findtext("a:summary", default="", namespaces=ATOM_NS)
        entries.append({
            "title": title,
            "link": link,
            "updated": updated,
            "summary": summary,
            "form_type": form_type,
        })
    return entries


def collect_insider_trades() -> list[dict]:
    """Form 4 récents : signal le plus réactif (dépôt sous 2 jours ouvrés après la transaction)."""
    try:
        return _fetch_current_filings("4")
    except Exception as e:
        print(f"[collect_edgar] Erreur Form 4 : {e}", file=sys.stderr)
        return []


def collect_13f_filings() -> list[dict]:
    """13F-HR récents : positions des institutionnels, mais mise à jour trimestrielle seulement."""
    try:
        time.sleep(0.5)  # éviter de marteler l'API sur deux appels successifs
        return _fetch_current_filings("13F-HR")
    except Exception as e:
        print(f"[collect_edgar] Erreur 13F : {e}", file=sys.stderr)
        return []


if __name__ == "__main__":
    insiders = collect_insider_trades()
    filings13f = collect_13f_filings()
    print(f"Form 4 récents : {len(insiders)}")
    print(f"13F-HR récents : {len(filings13f)}")
    for f in insiders[:5]:
        print(" -", f["title"])
