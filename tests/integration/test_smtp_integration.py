"""Integração com um servidor SMTP real (aiosmtpd rodando localmente)."""

import pytest

from emailme import email_me
from emailme.config import SmtpSettings
from emailme.errors import AuthenticationError, DeliveryError
from emailme.message import Email
from emailme.service import Mailer
from emailme.transport import SmtpTransport
from tests.conftest import LocalSmtpServer


def test_delivers_message_with_correct_envelope(smtp_server: LocalSmtpServer) -> None:
    transport = SmtpTransport(SmtpSettings.from_env(smtp_server.env()))
    email = Email.create(sender=smtp_server.username, recipients=["a@example.com", "b@example.com"])

    transport.send(email.to_mime())

    [received] = smtp_server.messages
    assert received.mail_from == smtp_server.username
    assert received.rcpt_tos == ["a@example.com", "b@example.com"]


def test_mailer_end_to_end(smtp_server: LocalSmtpServer) -> None:
    transport = SmtpTransport(SmtpSettings.from_env(smtp_server.env()))
    Mailer(transport, sender=smtp_server.username).send(subject="Oi", body="Corpo")

    [received] = smtp_server.messages
    parsed = received.parse()
    assert parsed["Subject"] == "Oi"
    assert parsed.get_content() == "Corpo\n"


def test_email_me_facade_against_real_server(smtp_server: LocalSmtpServer) -> None:
    email_me(smtp_server.username, "Assunto", "Corpo", env=smtp_server.env())

    [received] = smtp_server.messages
    assert received.rcpt_tos == [smtp_server.username]
    assert received.parse()["Subject"] == "Assunto"


def test_wrong_password_raises_authentication_error(smtp_server: LocalSmtpServer) -> None:
    settings = SmtpSettings.from_env(smtp_server.env(EMAILME_PASSWORD="wrong"))
    email = Email.create(sender=smtp_server.username)

    with pytest.raises(AuthenticationError):
        SmtpTransport(settings).send(email.to_mime())
    assert smtp_server.messages == []


def test_starttls_against_server_without_tls_fails_cleanly(
    smtp_server: LocalSmtpServer,
) -> None:
    settings = SmtpSettings.from_env(smtp_server.env(EMAILME_STARTTLS="true"))
    with pytest.raises(DeliveryError, match="STARTTLS"):
        SmtpTransport(settings).send(Email.create(sender=smtp_server.username).to_mime())


def test_unreachable_server_raises_delivery_error(unused_port: int) -> None:
    settings = SmtpSettings(
        username="eu@example.com",
        password="pw",
        host="127.0.0.1",
        port=unused_port,
        use_starttls=False,
        timeout=2,
    )
    with pytest.raises(DeliveryError, match=f"127.0.0.1:{unused_port}"):
        SmtpTransport(settings).send(Email.create(sender="eu@example.com").to_mime())
