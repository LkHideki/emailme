"""Interface de linha de comando: ``emailme`` / ``python -m emailme``."""

import argparse
import logging
import sys
from collections.abc import Callable, Mapping, Sequence
from enum import IntEnum
from typing import TextIO

from emailme import __version__
from emailme.api import load_environment
from emailme.config import ENV_USERNAME, SmtpSettings
from emailme.errors import ConfigurationError, DeliveryError, InvalidEmailError
from emailme.message import DEFAULT_BODY, DEFAULT_SUBJECT, Email
from emailme.service import Mailer
from emailme.transport import SmtpTransport, Transport

type TransportFactory = Callable[[SmtpSettings], Transport]


class ExitCode(IntEnum):
    OK = 0
    DELIVERY_ERROR = 1
    USAGE_ERROR = 2
    CONFIG_ERROR = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="emailme",
        description="Envia um email (por padrão, para você mesmo) via SMTP.",
    )
    parser.add_argument(
        "body",
        nargs="?",
        default=DEFAULT_BODY,
        help="corpo da mensagem; use '-' para ler da entrada padrão (padrão: %(default)r)",
    )
    parser.add_argument("-s", "--subject", default=DEFAULT_SUBJECT, help="assunto da mensagem")
    parser.add_argument(
        "-f",
        "--from",
        dest="sender",
        help=f"remetente e usuário SMTP (padrão: ${ENV_USERNAME})",
    )
    parser.add_argument(
        "-t",
        "--to",
        action="append",
        dest="recipients",
        metavar="ADDRESS",
        help="destinatário; pode ser repetido (padrão: o próprio remetente)",
    )
    parser.add_argument("--env-file", help="caminho de um arquivo .env alternativo")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="mostra a mensagem MIME sem enviar (não exige senha)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="exibe logs detalhados")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(  # noqa: PLR0913 - dependências injetáveis para testes
    argv: Sequence[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    transport_factory: TransportFactory = SmtpTransport,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Ponto de entrada da CLI. Devolve o código de saída em vez de chamar ``exit``."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
        stream=stderr,
    )

    def fail(code: ExitCode, message: str) -> int:
        print(f"emailme: error: {message}", file=stderr)
        return code

    environment = load_environment(args.env_file) if env is None else env
    sender = args.sender or environment.get(ENV_USERNAME)
    if not sender:
        return fail(ExitCode.CONFIG_ERROR, f"no sender given; use --from or set {ENV_USERNAME}")

    body = stdin.read() if args.body == "-" else args.body

    try:
        if args.dry_run:
            email = Email.create(
                sender=sender, recipients=args.recipients, subject=args.subject, body=body
            )
            stdout.write(email.to_mime().as_string())
            return ExitCode.OK

        settings = SmtpSettings.from_env(environment, username=sender)
        mailer = Mailer(transport_factory(settings), sender=sender)
        email = mailer.send(subject=args.subject, body=body, to=args.recipients)
    except InvalidEmailError as exc:
        return fail(ExitCode.USAGE_ERROR, str(exc))
    except ConfigurationError as exc:
        return fail(ExitCode.CONFIG_ERROR, str(exc))
    except DeliveryError as exc:
        return fail(ExitCode.DELIVERY_ERROR, str(exc))

    print(f"Email enviado com sucesso para {', '.join(email.recipients)}!", file=stdout)
    return ExitCode.OK


def run() -> None:  # pragma: no cover - wrapper fino usado pelo entry point
    sys.exit(main())
