from __future__ import annotations

import html
import json
import logging
import smtplib
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from email.utils import parseaddr
from threading import Lock
from typing import Literal, Protocol

from app.config import Settings, settings

logger = logging.getLogger(__name__)

EmailPurpose = Literal["verification", "password_reset"]


@dataclass(frozen=True)
class OutgoingEmail:
    recipient: str
    subject: str
    text_body: str
    html_body: str
    purpose: EmailPurpose | None = None


class EmailProvider(Protocol):
    def send(self, message: OutgoingEmail) -> None: ...


class EmailDeliveryError(RuntimeError):
    """An email provider could not accept a message; details are deliberately redacted."""


_test_outbox: list[OutgoingEmail] = []
_test_outbox_lock = Lock()


class _TestCaptureEmailProvider:
    """In-memory delivery for explicit, isolated E2E runs only."""

    def send(self, message: OutgoingEmail) -> None:
        with _test_outbox_lock:
            _test_outbox.append(message)
            del _test_outbox[:-100]


def take_test_email_link(recipient: str, purpose: EmailPurpose) -> str | None:
    with _test_outbox_lock:
        for index in range(len(_test_outbox) - 1, -1, -1):
            message = _test_outbox[index]
            if message.recipient.lower() != recipient.lower() or message.purpose != purpose:
                continue
            del _test_outbox[index]
            return next(
                (line for line in message.text_body.splitlines() if line.startswith("http")), None
            )
    return None


def _masked_recipient(address: str) -> str:
    _name, parsed = parseaddr(address)
    local, separator, domain = parsed.rpartition("@")
    if not separator or not local or not domain:
        return "<redacted>"
    return f"{local[0]}***@{domain}"


class ConsoleEmailProvider:
    def __init__(self, config: Settings = settings) -> None:
        self.config = config

    def send(self, message: OutgoingEmail) -> None:
        if self.config.app_env != "development":
            raise EmailDeliveryError("Console email delivery is available only in development")
        logger.info(
            "email provider=console recipient=%s subject=<redacted> body=<redacted>",
            _masked_recipient(message.recipient),
        )


class SMTPEmailProvider:
    def __init__(self, config: Settings = settings, timeout_seconds: float = 10) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds

    def send(self, message: OutgoingEmail) -> None:
        if not self.config.smtp_host:
            raise EmailDeliveryError("SMTP_HOST is required for SMTP delivery")

        mime = MimeMessage()
        mime["From"] = self.config.email_from
        mime["To"] = message.recipient
        mime["Subject"] = message.subject
        mime.set_content(message.text_body)
        mime.add_alternative(message.html_body, subtype="html")

        try:
            if self.config.smtp_use_ssl:
                server = smtplib.SMTP_SSL(
                    self.config.smtp_host,
                    self.config.smtp_port,
                    timeout=self.timeout_seconds,
                    context=ssl.create_default_context(),
                )
            else:
                server = smtplib.SMTP(
                    self.config.smtp_host,
                    self.config.smtp_port,
                    timeout=self.timeout_seconds,
                )
            with server:
                server.ehlo()
                if self.config.smtp_starttls and not self.config.smtp_use_ssl:
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                if self.config.smtp_username:
                    server.login(self.config.smtp_username, self.config.smtp_password or "")
                server.send_message(mime)
        except Exception:
            raise EmailDeliveryError("SMTP provider could not deliver the message") from None


class ResendEmailProvider:
    endpoint = "https://api.resend.com/emails"

    def __init__(self, config: Settings = settings, timeout_seconds: float = 10) -> None:
        self.config = config
        self.timeout_seconds = timeout_seconds

    def send(self, message: OutgoingEmail) -> None:
        if not self.config.resend_api_key:
            raise EmailDeliveryError("RESEND_API_KEY is required for Resend delivery")
        body = json.dumps(
            {
                "from": self.config.email_from,
                "to": [message.recipient],
                "subject": message.subject,
                "text": message.text_body,
                "html": message.html_body,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {self.config.resend_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                if not 200 <= response.status < 300:
                    raise EmailDeliveryError("Resend provider rejected the message")
        except EmailDeliveryError:
            raise
        except (OSError, urllib.error.URLError):
            raise EmailDeliveryError("Resend provider could not deliver the message") from None


def get_email_provider(config: Settings = settings) -> EmailProvider:
    if config.app_env == "test" and config.email_test_hook_enabled:
        return _TestCaptureEmailProvider()
    if config.email_provider == "console":
        return ConsoleEmailProvider(config)
    if config.email_provider == "smtp":
        return SMTPEmailProvider(config)
    if config.email_provider == "resend":
        return ResendEmailProvider(config)
    raise EmailDeliveryError("Unsupported email provider")


def provide_email_provider() -> EmailProvider:
    return get_email_provider(settings)


def auth_email(
    recipient: str,
    purpose: EmailPurpose,
    link: str,
    language: Literal["en", "hi"] = "en",
) -> OutgoingEmail:
    safe_link = html.escape(link, quote=True)
    if purpose == "verification" and language == "hi":
        subject = "Medical Passport ईमेल सत्यापन"
        text_body = (
            "अपने Medical Passport खाते का ईमेल सत्यापित करने के लिए इस लिंक को खोलें। "
            "यह लिंक 24 घंटे में समाप्त हो जाएगा।\n\n"
            f"{link}\n\nयदि आपने यह अनुरोध नहीं किया, तो इस ईमेल को अनदेखा करें।"
        )
        heading = "अपना ईमेल सत्यापित करें"
        action = "ईमेल सत्यापित करें"
        expiry = "यह लिंक 24 घंटे में समाप्त हो जाएगा।"
    elif purpose == "password_reset" and language == "hi":
        subject = "Medical Passport पासवर्ड रीसेट"
        text_body = (
            "अपना Medical Passport पासवर्ड रीसेट करने के लिए इस लिंक को खोलें। "
            "यह लिंक 30 मिनट में समाप्त हो जाएगा।\n\n"
            f"{link}\n\nयदि आपने यह अनुरोध नहीं किया, तो इस ईमेल को अनदेखा करें।"
        )
        heading = "पासवर्ड रीसेट करें"
        action = "पासवर्ड रीसेट करें"
        expiry = "यह लिंक 30 मिनट में समाप्त हो जाएगा।"
    elif purpose == "verification":
        subject = "Verify your Medical Passport email"
        text_body = (
            "Open this link to verify the email address for your Medical Passport account. "
            f"It expires in 24 hours.\n\n{link}\n\n"
            "If you did not request this, you can ignore this email."
        )
        heading = "Verify your email"
        action = "Verify email"
        expiry = "This link expires in 24 hours."
    else:
        subject = "Reset your Medical Passport password"
        text_body = (
            "Open this link to reset your Medical Passport password. "
            f"It expires in 30 minutes.\n\n{link}\n\n"
            "If you did not request this, you can ignore this email."
        )
        heading = "Reset your password"
        action = "Reset password"
        expiry = "This link expires in 30 minutes."

    html_body = (
        '<!doctype html><html lang="'
        + language
        + '"><body><main><h1>'
        + html.escape(heading)
        + '</h1><p><a href="'
        + safe_link
        + '">'
        + html.escape(action)
        + "</a></p><p>"
        + html.escape(expiry)
        + "</p></main></body></html>"
    )
    return OutgoingEmail(recipient, subject, text_body, html_body, purpose)
