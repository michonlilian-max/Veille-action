"""
Sentiment X (Twitter) en temps réel via l'API xAI (Grok) et sa fonctionnalité
"Live Search" — Grok interroge X directement et analyse les posts trouvés.

⚠️ CONTRAIREMENT À TOUTE LES AUTRES SOURCES DU PROJET, CELLE-CI N'EST PAS
GRATUITE. L'API xAI facture le modèle ET la recherche Live Search (par
source récupérée, en plus du coût du modèle). C'est la seule source
payante du pipeline — activée uniquement si le secret GROK_API_KEY est
configuré : si absent, ce signal contribue 0 au score et le reste du
pipeline continue normalement (même logique de dégradation que l'email).

⚠️ ATTENTION AU COÛT CUMULÉ SUR UN CRON AUTOMATIQUE : avec 16 tickers et le
planning par défaut (6 runs/jour en semaine), ça fait ~480 appels/semaine.
Vérifie ta conso réelle sur https://console.x.ai après quelques runs avant
de laisser tourner indéfiniment. Réduis GROK_MAX_SEARCH_RESULTS dans
config.py et/ou la fréquence du cron si le coût est trop élevé — voir le
README pour une estimation chiffrée.

Configure GROK_API_KEY comme secret GitHub Actions (jamais dans config.py,
qui est un fichier public du repo). Clé à générer sur https://console.x.ai
(nécessite une carte bancaire).

Doc API (peut évoluer, vérifie contre la doc officielle si ce script
casse) : https://docs.x.ai/docs/guides/live-search
"""
import json
import os
import time

import requests

from config import GROK_MAX_SEARCH_RESULTS, GROK_MODEL, WATCHLIST
from scripts.collect_edgar import get_company_title

XAI_API_URL = "https://api.x.ai/v1/chat/completions"

PROMPT_TEMPLATE = (
    "Analyse le sentiment des posts récents sur X (Twitter) à propos de "
    "l'action {ticker} ({company}). Réponds UNIQUEMENT avec un objet JSON, "
    "sans texte autour ni bloc de code, au format exact : "
    '{{"bullish_count": <nombre de posts plutôt haussiers/positifs>, '
    '"bearish_count": <nombre de posts plutôt baissiers/négatifs>, '
    '"post_count": <nombre total de posts pertinents analysés>, '
    '"summary": "<résumé en une phrase, en français>"}}'
)


def _clean_json_content(content):
    """Les LLM enveloppent parfois leur réponse dans un bloc ```json ... ```
    même quand on demande explicitement de ne pas le faire."""
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:]
        content = content.strip()
    return content


def collect_x_sentiment_for_ticker(ticker, api_key):
    company_title = get_company_title(ticker)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROK_MODEL,
        "messages": [
            {
                "role": "user",
                "content": PROMPT_TEMPLATE.format(ticker=ticker, company=company_title or ticker),
            }
        ],
        "search_parameters": {
            "mode": "on",
            "sources": [{"type": "x"}],
            "max_search_results": GROK_MAX_SEARCH_RESULTS,
        },
        "temperature": 0,
    }

    try:
        resp = requests.post(XAI_API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        content = _clean_json_content(data["choices"][0]["message"]["content"])
        parsed = json.loads(content)
        num_sources = (data.get("usage") or {}).get("num_sources_used")
        if num_sources is not None:
            print(f"[collect_grok_sentiment] {ticker} : {num_sources} sources X consultées")
        return {
            "ticker": ticker,
            "bullish": int(parsed.get("bullish_count", 0)),
            "bearish": int(parsed.get("bearish_count", 0)),
            "post_count": int(parsed.get("post_count", 0)),
            "summary": parsed.get("summary", ""),
        }
    except Exception as e:
        print(f"[collect_grok_sentiment] {ticker} : erreur ({e})")
        return None


def collect_all_x_sentiment(watchlist=None):
    """Renvoie {ticker: {...}}. Dict vide si GROK_API_KEY n'est pas
    configuré (signal ignoré, pas de crash). Un ticker en échec est
    simplement absent du résultat."""
    watchlist = watchlist or WATCHLIST
    api_key = os.environ.get("GROK_API_KEY")
    if not api_key:
        print("[collect_grok_sentiment] GROK_API_KEY absent — signal X ignoré (0 partout).")
        return {}

    results = {}
    for ticker in watchlist:
        entry = collect_x_sentiment_for_ticker(ticker, api_key)
        if entry:
            results[ticker] = entry
        time.sleep(0.5)  # chaque appel a un coût réel, pas la peine de se presser
    return results


if __name__ == "__main__":
    print(json.dumps(collect_all_x_sentiment(), indent=2, ensure_ascii=False))
