"""Fixtures compartilhadas entre as suítes de teste."""

import socket
from collections.abc import Iterator
from dataclasses import dataclass, field
from email import message_from_bytes, policy
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import pytest
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import AuthResult, LoginPassword
from hypothesis import HealthCheck, settings

TESTS_DIR = Path(__file__).parent

# Perfis do hypothesis: `--hypothesis-profile=ci` roda muito mais exemplos.
settings.register_profile("ci", max_examples=1000, deadline=None)
settings.register_profile("dev", max_examples=100, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile("dev")

# Cada subdiretório de testes recebe automaticamente o marker correspondente,
# permitindo rodar, por exemplo, apenas `pytest -m unit`.
_MARKERS_BY_DIR = ("unit", "property", "contract", "integration", "e2e")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        path = Path(str(item.path))
        if TESTS_DIR not in path.parents:
            continue
        kind = path.relative_to(TESTS_DIR).parts[0]
        if kind in _MARKERS_BY_DIR:
            item.add_marker(getattr(pytest.mark, kind))


# --------------------------------------------------------------------------- #
# Servidor SMTP local (aiosmtpd) para testes de integração, contrato e e2e
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class ReceivedMessage:
    mail_from: str
    rcpt_tos: list[str]
    raw: bytes

    def parse(self) -> EmailMessage:
        # No fio o SMTP usa CRLF; convertemos para \n antes de interpretar.
        native = self.raw.replace(b"\r\n", b"\n")
        return message_from_bytes(native, policy=policy.default)


@dataclass
class RecordingHandler:
    messages: list[ReceivedMessage] = field(default_factory=list)

    async def handle_DATA(self, server: Any, session: Any, envelope: Any) -> str:  # noqa: N802
        raw = envelope.original_content or envelope.content
        self.messages.append(ReceivedMessage(envelope.mail_from, list(envelope.rcpt_tos), raw))
        return "250 Message accepted for delivery"


@dataclass(frozen=True, slots=True)
class LocalSmtpServer:
    host: str
    port: int
    username: str
    password: str
    handler: RecordingHandler

    @property
    def messages(self) -> list[ReceivedMessage]:
        return self.handler.messages

    def env(self, **overrides: str) -> dict[str, str]:
        """Variáveis de ambiente que apontam o ``emailme`` para este servidor."""
        return {
            "EMAILME_USERNAME": self.username,
            "EMAILME_PASSWORD": self.password,
            "EMAILME_SMTP_HOST": self.host,
            "EMAILME_SMTP_PORT": str(self.port),
            "EMAILME_STARTTLS": "false",
            "EMAILME_TIMEOUT": "5",
        } | overrides


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _authenticator(username: str, password: str) -> Any:
    def authenticate(
        server: Any, session: Any, envelope: Any, mechanism: str, auth_data: Any
    ) -> AuthResult:
        ok = (
            isinstance(auth_data, LoginPassword)
            and auth_data.login == username.encode()
            and auth_data.password == password.encode()
        )
        return AuthResult(success=ok, handled=False)

    return authenticate


@pytest.fixture
def smtp_server() -> Iterator[LocalSmtpServer]:
    username, password = "tester@example.com", "app-password"
    handler = RecordingHandler()
    port = _free_port()
    controller = Controller(
        handler,
        hostname="127.0.0.1",
        port=port,
        authenticator=_authenticator(username, password),
        auth_required=True,
        auth_require_tls=False,
    )
    controller.start()
    try:
        yield LocalSmtpServer("127.0.0.1", port, username, password, handler)
    finally:
        controller.stop()


@pytest.fixture
def unused_port() -> int:
    """Uma porta local onde (muito provavelmente) nada está escutando."""
    return _free_port()
