import logging
from email.message import EmailMessage

import pytest

from emailme.errors import DeliveryError, InvalidEmailError
from emailme.service import Mailer
from emailme.transport import InMemoryTransport


class ExplodingTransport:
    def send(self, message: EmailMessage) -> None:
        raise DeliveryError("boom")


class TestMailer:
    def test_sends_to_self_by_default(self) -> None:
        transport = InMemoryTransport()
        email = Mailer(transport, sender="eu@example.com").send(subject="Oi", body="Corpo")

        [sent] = transport.outbox
        assert sent["To"] == "eu@example.com"
        assert sent["Subject"] == "Oi"
        assert email.recipients == ("eu@example.com",)

    def test_sends_to_explicit_recipients(self) -> None:
        transport = InMemoryTransport()
        Mailer(transport, sender="eu@example.com").send(to=["a@example.com", "b@example.com"])
        assert transport.outbox[0]["To"] == "a@example.com, b@example.com"

    def test_normalizes_sender(self) -> None:
        assert Mailer(InMemoryTransport(), sender=" eu@example.com ").sender == "eu@example.com"

    def test_rejects_invalid_sender_eagerly(self) -> None:
        with pytest.raises(InvalidEmailError):
            Mailer(InMemoryTransport(), sender="invalido")

    def test_invalid_message_is_not_sent(self) -> None:
        transport = InMemoryTransport()
        with pytest.raises(InvalidEmailError):
            Mailer(transport, sender="eu@example.com").send(subject="a\nb")
        assert transport.outbox == []

    def test_propagates_delivery_errors(self) -> None:
        with pytest.raises(DeliveryError, match="boom"):
            Mailer(ExplodingTransport(), sender="eu@example.com").send()

    def test_logs_successful_delivery(self, caplog: pytest.LogCaptureFixture) -> None:
        with caplog.at_level(logging.INFO, logger="emailme"):
            Mailer(InMemoryTransport(), sender="eu@example.com").send(subject="Assunto")
        assert "'Assunto' sent to eu@example.com" in caplog.text
