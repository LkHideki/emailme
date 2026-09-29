import smtplib
import ssl
from email.message import EmailMessage
from typing import Any, Self

import pytest

from emailme.config import SmtpSettings
from emailme.errors import AuthenticationError, DeliveryError
from emailme.message import Email
from emailme.transport import InMemoryTransport, SmtpTransport, Transport


class FakeSMTP:
    """Dublê de ``smtplib.SMTP`` que registra a sequência de chamadas."""

    instances: list[FakeSMTP]

    def __init__(self, host: str, port: int, *, timeout: float) -> None:
        self.host, self.port, self.timeout = host, port, timeout
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.closed = False
        type(self).instances.append(self)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.closed = True

    def ehlo(self) -> None:
        self.calls.append(("ehlo", ()))

    def starttls(self, *, context: ssl.SSLContext) -> None:
        self.calls.append(("starttls", (context,)))

    def login(self, user: str, password: str) -> None:
        self.calls.append(("login", (user, password)))

    def send_message(self, message: EmailMessage) -> None:
        self.calls.append(("send_message", (message,)))


class FailingSMTP(FakeSMTP):
    error: Exception

    def login(self, user: str, password: str) -> None:
        raise self.error


@pytest.fixture(autouse=True)
def _reset_fakes() -> None:
    FakeSMTP.instances = []


@pytest.fixture
def settings() -> SmtpSettings:
    return SmtpSettings(username="eu@example.com", password="pw", timeout=7)


@pytest.fixture
def message() -> EmailMessage:
    return Email.create(sender="eu@example.com").to_mime()


class TestSmtpTransport:
    def test_performs_starttls_handshake_before_login(
        self, settings: SmtpSettings, message: EmailMessage
    ) -> None:
        context = ssl.create_default_context()
        SmtpTransport(settings, smtp_factory=FakeSMTP, ssl_context=context).send(message)

        [smtp] = FakeSMTP.instances
        assert (smtp.host, smtp.port, smtp.timeout) == ("smtp.gmail.com", 587, 7)
        assert smtp.calls == [
            ("ehlo", ()),
            ("starttls", (context,)),
            ("ehlo", ()),
            ("login", ("eu@example.com", "pw")),
            ("send_message", (message,)),
        ]
        assert smtp.closed

    def test_default_tls_context_verifies_certificates(
        self, settings: SmtpSettings, message: EmailMessage
    ) -> None:
        SmtpTransport(settings, smtp_factory=FakeSMTP).send(message)
        [smtp] = FakeSMTP.instances
        context = smtp.calls[1][1][0]
        assert isinstance(context, ssl.SSLContext)
        assert context.verify_mode is ssl.CERT_REQUIRED
        assert context.check_hostname is True

    def test_can_skip_starttls(self, message: EmailMessage) -> None:
        settings = SmtpSettings(username="u@x.com", password="pw", use_starttls=False)
        SmtpTransport(settings, smtp_factory=FakeSMTP).send(message)
        [smtp] = FakeSMTP.instances
        assert [name for name, _ in smtp.calls] == ["ehlo", "login", "send_message"]

    def test_exposes_settings(self, settings: SmtpSettings) -> None:
        assert SmtpTransport(settings).settings is settings

    def test_maps_authentication_failure(
        self, settings: SmtpSettings, message: EmailMessage
    ) -> None:
        FailingSMTP.error = smtplib.SMTPAuthenticationError(535, b"bad credentials")
        with pytest.raises(AuthenticationError, match="rejected the credentials") as info:
            SmtpTransport(settings, smtp_factory=FailingSMTP).send(message)
        assert isinstance(info.value.__cause__, smtplib.SMTPAuthenticationError)
        assert FakeSMTP.instances[0].closed

    @pytest.mark.parametrize(
        "error",
        [
            smtplib.SMTPServerDisconnected("gone"),
            smtplib.SMTPRecipientsRefused({}),
            TimeoutError("timed out"),
        ],
    )
    def test_maps_smtp_and_network_errors(
        self, settings: SmtpSettings, message: EmailMessage, error: Exception
    ) -> None:
        FailingSMTP.error = error
        with pytest.raises(DeliveryError) as info:
            SmtpTransport(settings, smtp_factory=FailingSMTP).send(message)
        assert not isinstance(info.value, AuthenticationError)
        assert info.value.__cause__ is error

    def test_maps_connection_failure(self, settings: SmtpSettings, message: EmailMessage) -> None:
        def refuse(*args: object, **kwargs: object) -> smtplib.SMTP:
            raise ConnectionRefusedError("refused")

        with pytest.raises(DeliveryError, match=r"smtp\.gmail\.com:587"):
            SmtpTransport(settings, smtp_factory=refuse).send(message)

    def test_satisfies_transport_protocol(self, settings: SmtpSettings) -> None:
        assert isinstance(SmtpTransport(settings), Transport)


class TestInMemoryTransport:
    def test_records_messages_in_order(self) -> None:
        transport = InMemoryTransport()
        first = Email.create(sender="a@example.com").to_mime()
        second = Email.create(sender="b@example.com").to_mime()
        transport.send(first)
        transport.send(second)
        assert transport.outbox == [first, second]

    def test_satisfies_transport_protocol(self) -> None:
        assert isinstance(InMemoryTransport(), Transport)

    def test_arbitrary_objects_do_not_satisfy_protocol(self) -> None:
        assert not isinstance(object(), Transport)
