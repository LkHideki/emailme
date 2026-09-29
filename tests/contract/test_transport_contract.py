"""Testes de contrato: toda implementação de ``Transport`` deve se comportar igual.

Cada implementação é exercitada pelos mesmos testes, através de um adaptador que
sabe enviar e depois ler de volta o que foi entregue. Para adicionar um novo
transporte, basta adicionar um novo adaptador à fixture ``harness``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from email.message import EmailMessage

import pytest

from emailme.config import SmtpSettings
from emailme.message import Email
from emailme.transport import InMemoryTransport, SmtpTransport, Transport
from tests.conftest import LocalSmtpServer


@dataclass
class TransportHarness:
    transport: Transport
    delivered: Callable[[], list[EmailMessage]]


def _memory() -> TransportHarness:
    transport = InMemoryTransport()
    return TransportHarness(transport, lambda: list(transport.outbox))


def _smtp(server: LocalSmtpServer) -> TransportHarness:
    settings = SmtpSettings.from_env(server.env())
    return TransportHarness(SmtpTransport(settings), lambda: [m.parse() for m in server.messages])


@pytest.fixture(params=["memory", "smtp"])
def harness(request: pytest.FixtureRequest) -> TransportHarness:
    if request.param == "memory":
        return _memory()
    return _smtp(request.getfixturevalue("smtp_server"))


def test_implements_protocol(harness: TransportHarness) -> None:
    assert isinstance(harness.transport, Transport)


def test_nothing_delivered_before_send(harness: TransportHarness) -> None:
    assert harness.delivered() == []


def test_delivers_exactly_one_message_per_send(harness: TransportHarness) -> None:
    for i in range(3):
        harness.transport.send(Email.create(sender="eu@example.com", subject=f"#{i}").to_mime())
    assert [m["Subject"] for m in harness.delivered()] == ["#0", "#1", "#2"]


def test_preserves_headers_and_unicode_body(harness: TransportHarness) -> None:
    email = Email.create(
        sender="eu@example.com",
        recipients=["a@example.com", "b@example.com"],
        subject="Relatório diário ✅",
        body="Olá!\nTudo certo com o açaí.",
    )
    harness.transport.send(email.to_mime())

    [received] = harness.delivered()
    assert received["From"] == "eu@example.com"
    assert received["To"] == "a@example.com, b@example.com"
    assert received["Subject"] == "Relatório diário ✅"
    assert received.get_content() == "Olá!\nTudo certo com o açaí.\n"
