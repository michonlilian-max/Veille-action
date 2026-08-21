"""
Pondération temporelle : au lieu de compter un événement (achat
d'initié, article de presse) comme "présent/absent" dans une fenêtre
glissante, on lui donne un poids qui décroît avec son âge — un événement
d'aujourd'hui compte presque plein pot, un événement en fin de fenêtre
presque plus rien. Corrige un angle mort documenté depuis le début du
projet : sans ça, un Form 4 vieux de 29 jours pesait exactement pareil
qu'un d'hier dans le score, alors que ce projet cherche justement de
l'attention RÉCENTE, pas juste "dans les X derniers jours".

Décroissance exponentielle à demi-vie : le poids est divisé par 2 à
chaque intervalle de "half_life" écoulé. Un seul réglage à comprendre
par signal, et le poids ne tombe jamais brutalement à 0 comme le ferait
un filtre tout-ou-rien.
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def decay_weight(age_hours: float, half_life_hours: float) -> float:
    """1.0 si age_hours=0, 0.5 à age_hours=half_life_hours, 0.25 au
    double, etc. Jamais négatif. half_life_hours<=0 désactive la
    décroissance (poids toujours 1.0) plutôt que de diviser par zéro."""
    if half_life_hours <= 0:
        return 1.0
    return 0.5 ** (max(age_hours, 0.0) / half_life_hours)


def hours_since_rfc822(published: str, now: datetime) -> float | None:
    """Âge en heures d'une date au format RFC 822 (champ 'published' des
    flux RSS, cf. collect_news.py). None si la date est vide/invalide —
    l'appelant décide alors du poids par défaut (même principe que
    collect_news.py : un article sans date exploitable est gardé, pas
    rejeté à tort)."""
    if not published:
        return None
    try:
        dt = parsedate_to_datetime(published)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 3600


def hours_since_date(date_str: str, now: datetime, fmt: str = "%Y-%m-%d") -> float | None:
    """Âge en heures d'une date simple (ex: 'filing_date' des Form 4,
    cf. collect_edgar.py). None si invalide."""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    return (now - dt).total_seconds() / 3600
