"""Transportes: a camada de I/O responsável por efetivamente entregar mensagens.

O restante do pacote depende apenas do protocolo :class:`Transport`, o que
permite trocar o SMTP real por um transporte em memória nos testes (ou por
qualquer outro backend, como uma API HTTP de envio).
"""

import smtplib
import ssl
from collections.abc import Callable
from email.message import EmailMessage
from types import TracebackType
from typing import Protocol, Self, runtime_checkable

from emailme.config import SmtpSettings
from emailme.errors import AuthenticationError, DeliveryError


class SmtpClient(Protocol):
    """Subconjunto de :class:`smtplib.SMTP` usado pelo :class:`SmtpTransport`."""

    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    def ehlo(self) -> object: ...
    def starttls(self, *, context: ssl.SSLContext) -> object: ...
    def login(self, user: str, password: str) -> object: ...
    def send_message(self, msg: EmailMessage) -> object: ...


type SmtpFactory = Callable[..., SmtpClient]


@runtime_checkable
class Transport(Protocol):
    """Qualquer objeto capaz de entregar uma :class:`EmailMessage`."""

    def send(self, message: EmailMessage) -> None:
        """Entrega a mensagem ou levanta :class:`~emailme.errors.DeliveryError`."""
        ...


class SmtpTransport:
    """Entrega mensagens via SMTP, com STARTTLS e verificação de certificado."""

    def __init__(
        self,
        settings: SmtpSettings,
        *,
        smtp_factory: SmtpFactory = smtplib.SMTP,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self._settings = settings
        self._smtp_factory = smtp_factory
        self._ssl_context = ssl_context

    @property
    def settings(self) -> SmtpSettings:
        return self._settings

    def send(self, message: EmailMessage) -> None:
        s = self._settings
        try:
            with self._smtp_factory(s.host, s.port, timeout=s.timeout) as smtp:
                smtp.ehlo()
                if s.use_starttls:
                    smtp.starttls(context=self._ssl_context or ssl.create_default_context())
                    smtp.ehlo()
                smtp.login(s.username, s.password)
                smtp.send_message(message)
        except smtplib.SMTPAuthenticationError as exc:
            raise AuthenticationError(
                f"SMTP server {s.host}:{s.port} rejected the credentials for {s.username}"
            ) from exc
        except (smtplib.SMTPException, OSError) as exc:
            raise DeliveryError(f"could not deliver email via {s.host}:{s.port}: {exc}") from exc


class InMemoryTransport:
    """Transporte que apenas guarda as mensagens em memória.

    Útil em testes e em modo de simulação.

    >>> from emailme.message import Email
    >>> t = InMemoryTransport()
    >>> t.send(Email.create(sender="eu@example.com").to_mime())
    >>> len(t.outbox)
    1
    """

    def __init__(self) -> None:
        self.outbox: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)
