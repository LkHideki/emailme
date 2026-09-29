"""Hierarquia de exceções do pacote.

Todas as exceções públicas herdam de :class:`EmailMeError`, permitindo que quem
usa a biblioteca trate qualquer falha com um único ``except``.
"""


class EmailMeError(Exception):
    """Classe base para todos os erros do ``emailme``."""


class ConfigurationError(EmailMeError, OSError):
    """Configuração ausente ou inválida (ex.: senha de app não definida).

    Também herda de :class:`OSError` (``EnvironmentError``) para manter
    compatibilidade com a versão original, que levantava ``EnvironmentError``.
    """


class InvalidEmailError(EmailMeError, ValueError):
    """Os dados da mensagem (endereços, assunto) são inválidos."""


class DeliveryError(EmailMeError):
    """Falha ao entregar a mensagem ao servidor SMTP."""


class AuthenticationError(DeliveryError):
    """O servidor SMTP recusou as credenciais."""
