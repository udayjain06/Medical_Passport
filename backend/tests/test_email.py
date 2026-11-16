import json
import logging

import pytest
from app import email as email_module
from app.config import Settings
from app.email import (
    ConsoleEmailProvider,
    EmailDeliveryError,
    OutgoingEmail,
    ResendEmailProvider,
    SMTPEmailProvider,
    auth_email,
    get_email_provider,
    take_test_email_link,
)


def test_console_provider_logs_only_a_redacted_message(caplog):
    message = OutgoingEmail(
        "patient@example.com",
        "Verify your Medical Passport email",
        "https://app.example.test/verify?token=secret-token-value",
        "<a href='https://app.example.test/verify?token=secret-token-value'>Verify</a>",
    )

    with caplog.at_level(logging.INFO):
        ConsoleEmailProvider(Settings(app_env="development")).send(message)

    assert "p***@example.com" in caplog.text
    assert "<redacted>" in caplog.text
    assert "patient@example.com" not in caplog.text
    assert "secret-token-value" not in caplog.text
    assert "https://app.example.test" not in caplog.text


def test_console_provider_refuses_non_development():
    provider = ConsoleEmailProvider(Settings(app_env="test"))
    with pytest.raises(EmailDeliveryError, match="only in development"):
        provider.send(OutgoingEmail("person@example.com", "Subject", "Text", "<p>HTML</p>"))


@pytest.mark.parametrize(
    ("purpose", "language", "expected_subject", "expected_expiry"),
    [
        ("verification", "en", "Verify", "24 hours"),
        ("verification", "hi", "सत्यापन", "24 घंटे"),
        ("password_reset", "en", "Reset", "30 minutes"),
        ("password_reset", "hi", "रीसेट", "30 मिनट"),
    ],
)
def test_auth_email_templates_include_plain_text_and_minimal_html(
    purpose, language, expected_subject, expected_expiry
):
    message = auth_email(
        "person@example.com",
        purpose,
        "https://app.example.test/action?token=synthetic-token",
        language,
    )

    assert expected_subject in message.subject
    assert expected_expiry in message.text_body
    assert "synthetic-token" in message.text_body
    assert "<html" in message.html_body
    assert "<a href=" in message.html_body


def test_test_email_hook_retrieves_verification_link_with_api_purpose_name():
    recipient = "e2e-hook@example.test"
    provider = get_email_provider(Settings(app_env="test", email_test_hook_enabled=True))
    provider.send(
        auth_email(
            recipient,
            "verification",
            "https://app.example.test/verify-email?token=synthetic-hook-token",
        )
    )

    assert take_test_email_link(recipient, "email_verification") == (
        "https://app.example.test/verify-email?token=synthetic-hook-token"
    )
    assert take_test_email_link(recipient, "email_verification") is None


def test_smtp_provider_sends_multipart_message(monkeypatch):
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, **kwargs):
            assert (host, port) == ("smtp.example.test", 587)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def ehlo(self):
            return None

        def starttls(self, **_kwargs):
            return None

        def login(self, username, password):
            assert (username, password) == ("mailer", "smtp-secret")

        def send_message(self, message):
            sent.append(message)

    monkeypatch.setattr(email_module.smtplib, "SMTP", FakeSMTP)
    config = Settings(
        app_env="development",
        email_provider="smtp",
        smtp_host="smtp.example.test",
        smtp_username="mailer",
        smtp_password="smtp-secret",
    )
    SMTPEmailProvider(config).send(
        OutgoingEmail("person@example.test", "Subject", "Text part", "<p>HTML part</p>")
    )

    assert len(sent) == 1
    assert sent[0].get_content_type() == "multipart/alternative"
    assert "Text part" in sent[0].as_string()
    assert "HTML part" in sent[0].as_string()


def test_provider_factory_selects_configured_delivery_adapter():
    assert isinstance(
        get_email_provider(Settings(app_env="development", email_provider="console")),
        ConsoleEmailProvider,
    )
    assert isinstance(
        get_email_provider(
            Settings(app_env="development", email_provider="smtp", smtp_host="smtp.test")
        ),
        SMTPEmailProvider,
    )
    assert isinstance(
        get_email_provider(
            Settings(app_env="development", email_provider="resend", resend_api_key="test-key")
        ),
        ResendEmailProvider,
    )


def test_smtp_delivery_error_does_not_expose_provider_details(monkeypatch):
    class BrokenSMTP:
        def __init__(self, *_args, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def ehlo(self):
            return None

        def starttls(self, **_kwargs):
            return None

        def send_message(self, _message):
            raise RuntimeError("smtp credential=synthetic-secret")

    monkeypatch.setattr(email_module.smtplib, "SMTP", BrokenSMTP)
    provider = SMTPEmailProvider(
        Settings(app_env="development", email_provider="smtp", smtp_host="smtp.example.test")
    )

    with pytest.raises(EmailDeliveryError, match="could not deliver") as error:
        provider.send(OutgoingEmail("person@example.test", "Subject", "Text", "<p>HTML</p>"))
    assert "synthetic-secret" not in str(error.value)


def test_resend_provider_posts_both_body_formats_without_logging_secret(monkeypatch):
    requests = []

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr(email_module.urllib.request, "urlopen", fake_urlopen)
    config = Settings(
        app_env="development",
        email_provider="resend",
        resend_api_key="resend-secret",
    )
    message = OutgoingEmail("person@example.test", "Subject", "Text", "<p>HTML</p>")
    ResendEmailProvider(config).send(message)

    request, timeout = requests[0]
    payload = json.loads(request.data)
    assert request.full_url == "https://api.resend.com/emails"
    assert request.get_header("Authorization") == "Bearer resend-secret"
    assert payload["text"] == "Text" and payload["html"] == "<p>HTML</p>"
    assert timeout == 10


def test_resend_delivery_error_does_not_expose_provider_details(monkeypatch):
    def fail(_request, timeout):
        del timeout
        raise email_module.urllib.error.URLError("resend credential=synthetic-secret")

    monkeypatch.setattr(email_module.urllib.request, "urlopen", fail)
    provider = ResendEmailProvider(
        Settings(app_env="development", email_provider="resend", resend_api_key="test-key")
    )

    with pytest.raises(EmailDeliveryError, match="could not deliver") as error:
        provider.send(OutgoingEmail("person@example.test", "Subject", "Text", "<p>HTML</p>"))
    assert "synthetic-secret" not in str(error.value)
