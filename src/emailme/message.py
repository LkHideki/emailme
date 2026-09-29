"""Modelo de domínio da mensagem de email.

:class:`Email` é um valor imutável e validado; a conversão para o formato MIME
da biblioteca padrão acontece apenas em :meth:`Email.to_mime`.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Self

from emailme.errors import InvalidEmailError

DEFAULT_SUBJECT = "Automatic Email via Python"
DEFAULT_BODY = "Hello"


def validate_address(address: str) -> str:
    """Valida (de forma pragmática) um endereço de email e o devolve normalizado.

    >>> validate_address("  eu@example.com ")
    'eu@example.com'
    >>> validate_address("sem-arroba")
    Traceback (most recent call last):
    ...
    emailme.errors.InvalidEmailError: invalid email address: 'sem-arroba'
    """
    if "\r" in address or "\n" in address:
        raise InvalidEmailError(f"email address contains line breaks: {address!r}")
    candidate = address.strip()
    _, parsed = parseaddr(candidate)
    local, at, domain = parsed.rpartition("@")
    if not (parsed and at and local and domain) or parsed != candidate or " " in parsed:
        raise InvalidEmailError(f"invalid email address: {address!r}")
    return parsed


@dataclass(frozen=True, slots=True, kw_only=True)
class Email:
    """Uma mensagem de texto simples pronta para envio.

    >>> msg = Email.create(sender="eu@example.com", subject="Oi", body="Olá!")
    >>> msg.recipients
    ('eu@example.com',)
    >>> msg.to_mime()["Subject"]
    'Oi'
    """

    sender: str
    recipients: tuple[str, ...]
    subject: str = DEFAULT_SUBJECT
    body: str = DEFAULT_BODY

    def __post_init__(self) -> None:
        validate_address(self.sender)
        if not self.recipients:
            raise InvalidEmailError("at least one recipient is required")
        for recipient in self.recipients:
            validate_address(recipient)
        if "\r" in self.subject or "\n" in self.subject:
            raise InvalidEmailError("subject must not contain line breaks")

    @classmethod
    def create(
        cls,
        *,
        sender: str,
        recipients: Iterable[str] | None = None,
        subject: str = DEFAULT_SUBJECT,
        body: str = DEFAULT_BODY,
    ) -> Self:
        """Cria a mensagem normalizando endereços.

        Sem ``recipients``, a mensagem é endereçada ao próprio remetente.
        """
        normalized_sender = validate_address(sender)
        targets = (
            (normalized_sender,)
            if recipients is None
            else tuple(dict.fromkeys(validate_address(r) for r in recipients))
        )
        return cls(sender=normalized_sender, recipients=targets, subject=subject, body=body)

    def to_mime(self) -> EmailMessage:
        """Converte para :class:`email.message.EmailMessage` (UTF-8, texto puro)."""
        mime = EmailMessage()
        mime["From"] = self.sender
        mime["To"] = ", ".join(self.recipients)
        mime["Subject"] = self.subject
        mime.set_content(self.body, subtype="plain", charset="utf-8")
        return mime
