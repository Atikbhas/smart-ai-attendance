import smtplib
from email.message import EmailMessage

from flask import current_app


def send_email(subject: str, recipients: list[str], html_body: str, text_body: str | None = None) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = current_app.config["MAIL_DEFAULT_SENDER"]
    message["To"] = ", ".join(recipients)
    message.set_content(text_body or html_body, subtype="plain")
    message.add_alternative(html_body, subtype="html")

    mail_server = current_app.config.get("MAIL_SERVER")
    mail_port = current_app.config.get("MAIL_PORT")
    if not mail_server or not mail_port:
        raise RuntimeError("Email configuration is incomplete.")

    use_ssl = current_app.config.get("MAIL_USE_SSL", False)
    use_tls = current_app.config.get("MAIL_USE_TLS", False)
    username = current_app.config.get("MAIL_USERNAME")
    password = current_app.config.get("MAIL_PASSWORD")

    if use_ssl:
        smtp = smtplib.SMTP_SSL(mail_server, mail_port, timeout=10)
    else:
        smtp = smtplib.SMTP(mail_server, mail_port, timeout=10)
        if use_tls:
            smtp.starttls()

    try:
        if username and password:
            smtp.login(username, password)
        smtp.send_message(message)
    finally:
        smtp.quit()
