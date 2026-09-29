"""API de alto nível, compatível com a função original ``email_me``."""

import os
from collections.abc import Mapping
from pathlib import Path

from dotenv import dotenv_values, find_dotenv

from emailme.config import SmtpSettings
from emailme.message import DEFAULT_BODY, DEFAULT_SUBJECT, Email
from emailme.service import Mailer
from emailme.transport import SmtpTransport, Transport


def load_environment(dotenv_path: str | Path | None = None) -> dict[str, str]:
    """Combina o arquivo ``.env`` com ``os.environ`` (o ambiente tem precedência).

    Diferente de ``load_dotenv``, não altera ``os.environ`` como efeito colateral.
    """
    path = dotenv_path if dotenv_path is not None else find_dotenv(usecwd=True)
    from_file = {k: v for k, v in dotenv_values(path).items() if v is not None} if path else {}
    return from_file | dict(os.environ)


def email_me(
    address: str,
    subject: str = DEFAULT_SUBJECT,
    body: str = DEFAULT_BODY,
    *,
    transport: Transport | None = None,
    env: Mapping[str, str] | None = None,
) -> Email:
    """Envia um email para o próprio ``address`` usando SMTP (Gmail por padrão).

    A senha de app é lida de ``EMAILME_PASSWORD`` (ou ``SENHA_DE_APP_GMAIL``),
    no ambiente ou em um arquivo ``.env`` no diretório atual.

    Parameters:
    - address: endereço usado como remetente, destinatário e usuário SMTP.
    - subject: assunto da mensagem.
    - body: corpo em texto puro.
    - transport: transporte alternativo (ex.: ``InMemoryTransport`` em testes).
    - env: variáveis de ambiente a usar no lugar de ``.env`` + ``os.environ``.

    Returns a mensagem enviada.
    """
    if transport is None:
        settings = SmtpSettings.from_env(
            load_environment() if env is None else env, username=address
        )
        transport = SmtpTransport(settings)
    return Mailer(transport, sender=address).send(subject=subject, body=body)
