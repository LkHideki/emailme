"""Configuração do transporte SMTP.

A configuração é um objeto imutável e validado na construção. A leitura de
variáveis de ambiente fica isolada em :meth:`SmtpSettings.from_env`, que recebe
o ``Mapping`` explicitamente — o que torna o código trivial de testar.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Self

from emailme.errors import ConfigurationError

DEFAULT_HOST = "smtp.gmail.com"
DEFAULT_PORT = 587
DEFAULT_TIMEOUT = 30.0

# Nomes das variáveis de ambiente suportadas.
ENV_USERNAME = "EMAILME_USERNAME"
ENV_PASSWORD = "EMAILME_PASSWORD"  # noqa: S105 - nome da variável, não a senha
ENV_PASSWORD_LEGACY = "SENHA_DE_APP_GMAIL"  # noqa: S105
ENV_HOST = "EMAILME_SMTP_HOST"
ENV_PORT = "EMAILME_SMTP_PORT"
ENV_STARTTLS = "EMAILME_STARTTLS"
ENV_TIMEOUT = "EMAILME_TIMEOUT"

_TRUE = frozenset({"1", "true", "yes", "on", "sim"})
_FALSE = frozenset({"0", "false", "no", "off", "nao", "não"})


@dataclass(frozen=True, slots=True, kw_only=True)
class SmtpSettings:
    """Parâmetros de conexão e autenticação SMTP.

    >>> s = SmtpSettings(username="eu@example.com", password="segredo")
    >>> s.host, s.port, s.use_starttls
    ('smtp.gmail.com', 587, True)
    >>> "segredo" in repr(s)
    False
    """

    username: str
    password: str = field(repr=False)
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    use_starttls: bool = True
    timeout: float = DEFAULT_TIMEOUT

    def __post_init__(self) -> None:
        if not self.username.strip():
            raise ConfigurationError("SMTP username must not be empty")
        if not self.password:
            raise ConfigurationError("SMTP password must not be empty")
        if not self.host.strip():
            raise ConfigurationError("SMTP host must not be empty")
        if not 0 < self.port < 65536:
            raise ConfigurationError(f"SMTP port out of range: {self.port}")
        if self.timeout <= 0:
            raise ConfigurationError(f"SMTP timeout must be positive: {self.timeout}")

    @classmethod
    def from_env(cls, env: Mapping[str, str], *, username: str | None = None) -> Self:
        """Constrói as configurações a partir de um mapeamento de variáveis.

        ``username`` tem precedência sobre ``EMAILME_USERNAME``. A senha é lida de
        ``EMAILME_PASSWORD`` ou, por compatibilidade, de ``SENHA_DE_APP_GMAIL``.
        """
        user = username or env.get(ENV_USERNAME)
        if not user:
            raise ConfigurationError(f"{ENV_USERNAME} is not set and no username was given")

        password = env.get(ENV_PASSWORD) or env.get(ENV_PASSWORD_LEGACY)
        if not password:
            raise ConfigurationError(
                f"{ENV_PASSWORD} (or legacy {ENV_PASSWORD_LEGACY}) is missing from the environment"
            )

        return cls(
            username=user,
            password=password,
            host=env.get(ENV_HOST) or DEFAULT_HOST,
            port=_parse_int(env, ENV_PORT, DEFAULT_PORT),
            use_starttls=_parse_bool(env, ENV_STARTTLS, default=True),
            timeout=_parse_float(env, ENV_TIMEOUT, DEFAULT_TIMEOUT),
        )


def _parse_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        raise ConfigurationError(f"{key} must be an integer, got {raw!r}") from None


def _parse_float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        raise ConfigurationError(f"{key} must be a number, got {raw!r}") from None


def _parse_bool(env: Mapping[str, str], key: str, *, default: bool) -> bool:
    raw = env.get(key)
    if raw is None or not raw.strip():
        return default
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    raise ConfigurationError(f"{key} must be a boolean, got {raw!r}")
