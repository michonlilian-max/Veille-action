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


def send_report(output):
    server = os.environ.get("SMTP_SERVER")
    port = os.environ.get("SMTP_PORT")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    to_addrs = os.environ.get("EMAIL_TO")

    if not all([server, port, user, password, to_addrs]):
        print("[send_email] Variables SMTP manquantes (SMTP_SERVER/PORT/USER/PASSWORD/EMAIL_TO) — envoi ignoré.")
        return

    recipients = [addr.strip() for addr in to_addrs.split(",") if addr.strip()]
    body = build_report_text(output)

    msg = MIMEMultipart()
    msg["From"] = user
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = f"Veille Actions — rapport du {output['generated_at'][:10]}"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(server, int(port), context=context) as smtp:
            smtp.login(user, password)
            smtp.sendmail(user, recipients, msg.as_string())
        print(f"[send_email] Email envoyé à {', '.join(recipients)}")
    except Exception as e:
        print(f"[send_email] Erreur d'envoi : {e}")


if __name__ == "__main__":
    import json

    with open("data/output.json", encoding="utf-8") as f:
        data = json.load(f)
    send_report(data)
