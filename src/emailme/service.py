"""Camada de aplicação: orquestra criação e envio de mensagens."""

import logging
from collections.abc import Iterable

from emailme.message import DEFAULT_BODY, DEFAULT_SUBJECT, Email
from emailme.transport import Transport

logger = logging.getLogger(__name__)


class Mailer:
    """Envia mensagens de um remetente fixo através de um :class:`Transport`."""

    def __init__(self, transport: Transport, *, sender: str) -> None:
        self._transport = transport
        # Valida o remetente cedo, antes de qualquer envio.
        self._sender = Email.create(sender=sender).sender

    @property
    def sender(self) -> str:
        return self._sender

    def send(
        self,
        *,
        subject: str = DEFAULT_SUBJECT,
        body: str = DEFAULT_BODY,
        to: Iterable[str] | None = None,
    ) -> Email:
        """Envia uma mensagem; sem ``to``, envia para o próprio remetente."""
        email = Email.create(sender=self._sender, recipients=to, subject=subject, body=body)
        self._transport.send(email.to_mime())
        logger.info("Email %r sent to %s", email.subject, ", ".join(email.recipients))
        return email
