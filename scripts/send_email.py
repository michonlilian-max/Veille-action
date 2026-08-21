"""
Envoie un email récapitulatif du dernier run (score composite + explication
en clair de ce qui pousse chaque ticker) via SMTP.

100% gratuit : utilise ta propre boîte mail (Gmail, Yahoo Mail, Outlook...)
avec un "mot de passe d'application", pas de service tiers payant (pas de
SendGrid, Mailgun, etc.).

Variables d'environnement requises (à définir en secrets GitHub Actions,
JAMAIS en clair dans config.py qui est public — voir README) :
  SMTP_SERVER   ex: smtp.mail.yahoo.com (Gmail: smtp.gmail.com)
  SMTP_PORT     ex: 465
  SMTP_USER     ton adresse email (expéditeur ET identifiant de connexion)
  SMTP_PASSWORD ton mot de passe d'application (PAS ton mot de passe normal)
  EMAIL_TO      adresse(s) destinataire(s), séparées par des virgules

Si une seule de ces variables manque, l'envoi est silencieusement ignoré
(pour ne pas faire échouer tout le pipeline si l'email n'est pas configuré).
"""
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SIGNAL_LABELS = {
    "sentiment_social": "le sentiment social (StockTwits)",
    "news_volume": "le volume de news récentes",
    "insider_buying": "de vrais achats d'initiés récents (Form 4)",
    "institutional_13f": "une présence dans un 13F récent",
    "volume_spike": "un volume d'échange anormal / une forte variation de prix",
    "sentiment_x": "le sentiment réel sur X (analysé par Grok)",
}


def _explain(row):
    """Génère une phrase expliquant pourquoi ce ticker a ce score, en
    identifiant le signal qui y contribue le plus."""
    detail = row["detail"]
    top_signal = max(detail, key=detail.get)
    if detail[top_signal] == 0:
        return "Aucun signal notable détecté sur cette période."
    return f"Porté surtout par {SIGNAL_LABELS[top_signal]} ({detail[top_signal]}/100)."


def build_report_text(output):
    """Construit le corps de l'email en texte brut à partir de output.json."""
    lines = [
        "VEILLE ACTIONS — Rapport automatique",
        f"Généré le {output['generated_at']}",
        "",
        output["disclaimer"],
        "",
        "=" * 60,
    ]
    for row in output["watchlist"]:
        detail = row["detail"]
        lines.append(f"\n{row['ticker']} — score {row['score']}/100")
        lines.append(f"  {_explain(row)}")
        if row.get("price") is not None:
            sign = "+" if (row.get("change_pct") or 0) >= 0 else ""
            lines.append(
                f"  Prix : {row['price']} $ ({sign}{row.get('change_pct', 0)}% sur 1j, "
                f"volume x{row.get('volume_ratio', 1)} vs moyenne)"
            )
        if row.get("x_summary"):
            lines.append(f"  X (Grok) : {row['x_summary']}")
        lines.append(
            "  Détail : sentiment {sentiment_social} | news {news_volume} | "
            "insiders {insider_buying} | 13F {institutional_13f} | "
            "volume {volume_spike} | X {sentiment_x} "
            "({news_count} articles récents)".format(
                news_count=row["news_count"], **detail
            )
        )
    return "\n".join(lines)


def _send_email(subject, body):
    """Envoi SMTP générique, partagé par tous les rapports email du projet
    (veille + paper trading). Dégradation gracieuse si les variables SMTP
    ne sont pas configurées — même logique dans tous les cas d'usage."""
    server = os.environ.get("SMTP_SERVER")
    port = os.environ.get("SMTP_PORT")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    to_addrs = os.environ.get("EMAIL_TO")

    if not all([server, port, user, password, to_addrs]):
        print("[send_email] Variables SMTP manquantes (SMTP_SERVER/PORT/USER/PASSWORD/EMAIL_TO) — envoi ignoré.")
        return

    recipients = [addr.strip() for addr in to_addrs.split(",") if addr.strip()]

    msg = MIMEMultipart()
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(server, int(port), context=context) as smtp:
            smtp.login(user, password)
            smtp.sendmail(user, recipients, msg.as_string())
        print(f"[send_email] Email envoyé à {', '.join(recipients)} — {subject}")
    except Exception as e:
        print(f"[send_email] Erreur d'envoi : {e}")


def send_report(output):
    body = build_report_text(output)
    subject = f"Veille Actions — rapport du {output['generated_at'][:10]}"
    _send_email(subject, body)


def build_paper_trade_report_text(day_record, summary):
    """Construit le corps de l'email récapitulatif quotidien du bot de
    paper trading, à partir du journal du jour (complété par
    scripts/check_paper_trade_exits.py) et du résumé cumulé.

    Le bot tient des positions flexibles (pas de "tout revendre chaque
    soir") : ce rapport distingue les nouvelles entrées du jour, les
    sorties réelles (take-profit/stop-loss déclenché) et les positions
    toujours ouvertes (dont la performance n'est pas encore réalisée)."""
    date = day_record["date"]
    equity_open = day_record.get("equity_at_open")
    equity_close = day_record.get("equity_at_close")
    day_pct = (
        round(100 * (equity_close - equity_open) / equity_open, 2)
        if equity_open and equity_close is not None else None
    )
    sign = "+" if (day_pct or 0) >= 0 else ""

    entries = day_record.get("entries", [])
    exits = day_record.get("exits", [])
    holdings = summary.get("current_holdings", [])

    lines = [
        "VEILLE ACTIONS — Bot de trading (PAPER TRADING — aucun argent réel)",
        f"Récapitulatif du {date}",
        "",
        "⚠️ Portefeuille simulé. Aucune de ces valeurs ne représente de l'argent réel.",
        "",
        "=" * 60,
        "",
        f"Performance du compte aujourd'hui : {sign}{day_pct}%" if day_pct is not None else "Performance du compte aujourd'hui : n/a",
        f"  Équité à l'ouverture : {equity_open:.2f} $" if equity_open is not None else "  Équité à l'ouverture : n/a",
        f"  Équité à la clôture : {equity_close:.2f} $" if equity_close is not None else "  Équité à la clôture : n/a",
        "",
    ]

    if entries:
        lines.append(f"Nouvelles positions ouvertes aujourd'hui ({len(entries)}) :")
        for e in entries:
            lines.append(f"  {e['ticker']} — {e.get('notional', 0):.2f} $")
        lines.append("")

    if exits:
        lines.append(f"Positions fermées aujourd'hui ({len(exits)}) :")
        for x in exits:
            label = "take-profit" if x.get("reason") == "take_profit" else "stop-loss"
            xsign = "+" if (x.get("unrealized_plpc") or 0) >= 0 else ""
            lines.append(f"  {x['ticker']} — {label} déclenché, {xsign}{x.get('unrealized_plpc')}%")
        lines.append("")
    else:
        lines.append("Aucune position fermée aujourd'hui (rien n'a atteint le seuil de "
                      "take-profit ou de stop-loss).")
        lines.append("")

    if holdings:
        lines.append(f"Positions actuellement ouvertes ({len(holdings)}, performance non réalisée) :")
        for h in holdings:
            hsign = "+" if (h.get("unrealized_plpc") or 0) >= 0 else ""
            lines.append(f"  {h['ticker']} — {hsign}{h.get('unrealized_plpc')}%")
        lines.append("")

    lines += [
        "-" * 60,
        "",
        f"Performance cumulée depuis le début : "
        f"{'+' if (summary.get('total_return_pct') or 0) >= 0 else ''}{summary.get('total_return_pct')}% "
        f"({summary.get('days_tracked')} jours suivis)",
        f"Équité actuelle : {summary.get('current_equity'):.2f} $" if summary.get("current_equity") is not None else "",
        f"Équité de départ : {summary.get('starting_equity'):.2f} $" if summary.get("starting_equity") is not None else "",
    ]
    return "\n".join(lines)


def send_paper_trade_report(day_record, summary):
    body = build_paper_trade_report_text(day_record, summary)
    subject = f"Veille Actions — bot paper trading, récap du {day_record['date']}"
    _send_email(subject, body)


if __name__ == "__main__":
    import json

    with open("data/output.json", encoding="utf-8") as f:
        data = json.load(f)
    send_report(data)
