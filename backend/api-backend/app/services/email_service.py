"""Envío de correo (verificación). Sin SMTP configurado solo se registra el enlace en logs."""
import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import config

logger = logging.getLogger(__name__)


def _send_smtp_sync(to_email: str, subject: str, text_body: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if config.SMTP_USE_TLS:
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30)
        try:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_FROM, [to_email], msg.as_string())
        finally:
            server.quit()
    else:
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30)
        try:
            if config.SMTP_USER:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_FROM, [to_email], msg.as_string())
        finally:
            server.quit()


async def send_verification_email(to_email: str, token: str, recipient_name: str) -> None:
    link = f"{config.FRONTEND_BASE_URL}/verify-email?token={token}"
    subject = "Verificá tu correo — SmartBooking"
    text_body = (
        f"Hola {recipient_name},\n\n"
        f"Para activar tu cuenta abrí este enlace:\n{link}\n\n"
        "Si no creaste la cuenta, ignorá este mensaje.\n"
    )
    html_body = (
        f"<p>Hola {recipient_name},</p>"
        f'<p>Para activar tu cuenta hacé clic en '
        f'<a href="{link}">verificar correo</a>.</p>'
        "<p>Si no creaste la cuenta, ignorá este mensaje.</p>"
    )

    if not config.SMTP_HOST:
        logger.warning(
            "SMTP_HOST no configurado; enlace de verificación para %s: %s",
            to_email,
            link,
        )
        return

    await asyncio.to_thread(_send_smtp_sync, to_email, subject, text_body, html_body)
    logger.info("Correo de verificación enviado a %s", to_email)
