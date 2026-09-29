"""emailme — envio simples de emails para si mesmo via SMTP.

Uso rápido::

    from emailme import email_me

    email_me("seu_email@gmail.com", "Assunto", "Corpo")
"""

import logging
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("emailme")
except PackageNotFoundError:  # pragma: no cover - pacote não instalado
    __version__ = "0.0.0"

from emailme.api import email_me, load_environment
from emailme.config import SmtpSettings
from emailme.errors import (
    AuthenticationError,
    ConfigurationError,
    DeliveryError,
    EmailMeError,
    InvalidEmailError,
)
from emailme.message import Email
from emailme.service import Mailer
from emailme.transport import InMemoryTransport, SmtpTransport, Transport

logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = [
    "AuthenticationError",
    "ConfigurationError",
    "DeliveryError",
    "Email",
    "EmailMeError",
    "InMemoryTransport",
    "InvalidEmailError",
    "Mailer",
    "SmtpSettings",
    "SmtpTransport",
    "Transport",
    "__version__",
    "email_me",
    "load_environment",
]
