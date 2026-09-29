import io
from email import message_from_string, policy
from email.message import EmailMessage

import pytest

import emailme
from emailme.cli import ExitCode, build_parser, main
from emailme.config import SmtpSettings
from emailme.errors import AuthenticationError
from emailme.transport import InMemoryTransport

BASE_ENV = {"EMAILME_USERNAME": "eu@example.com", "EMAILME_PASSWORD": "pw"}


class Harness:
    """Executa ``main`` em processo, capturando I/O e o transporte usado."""

    def __init__(self) -> None:
        self.transport = InMemoryTransport()
        self.settings: SmtpSettings | None = None
        self.stdout = io.StringIO()
        self.stderr = io.StringIO()

    def factory(self, settings: SmtpSettings) -> InMemoryTransport:
        self.settings = settings
        return self.transport

    def __call__(self, *argv: str, env: dict[str, str] | None = None, stdin: str = "") -> int:
        return main(
            list(argv),
            env=BASE_ENV if env is None else env,
            transport_factory=self.factory,
            stdin=io.StringIO(stdin),
            stdout=self.stdout,
            stderr=self.stderr,
        )

    @property
    def sent(self) -> list[EmailMessage]:
        return self.transport.outbox


@pytest.fixture
def cli() -> Harness:
    return Harness()


class TestSend:
    def test_sends_to_self_with_defaults(self, cli: Harness) -> None:
        assert cli() == ExitCode.OK

        [message] = cli.sent
        assert message["To"] == "eu@example.com"
        assert message["Subject"] == "Automatic Email via Python"
        assert message.get_content() == "Hello\n"
        assert "sucesso" in cli.stdout.getvalue()
        assert cli.settings is not None
        assert cli.settings.password == "pw"

    def test_custom_subject_body_and_recipients(self, cli: Harness) -> None:
        code = cli("Corpo", "-s", "Assunto", "--to", "a@example.com", "-t", "b@example.com")

        assert code == ExitCode.OK
        [message] = cli.sent
        assert message["To"] == "a@example.com, b@example.com"
        assert message["Subject"] == "Assunto"
        assert message.get_content() == "Corpo\n"

    def test_reads_body_from_stdin(self, cli: Harness) -> None:
        assert cli("-", stdin="vindo do stdin\n") == ExitCode.OK
        assert cli.sent[0].get_content() == "vindo do stdin\n"

    def test_from_flag_overrides_environment_username(self, cli: Harness) -> None:
        assert cli("--from", "outro@example.com") == ExitCode.OK
        assert cli.sent[0]["From"] == "outro@example.com"
        assert cli.settings is not None
        assert cli.settings.username == "outro@example.com"


class TestDryRun:
    def test_prints_mime_message_without_sending(self, cli: Harness) -> None:
        code = cli("Corpo", "-s", "Teste", "--dry-run", env={"EMAILME_USERNAME": "eu@example.com"})

        assert code == ExitCode.OK
        assert cli.sent == []
        parsed = message_from_string(cli.stdout.getvalue(), policy=policy.default)
        assert parsed["Subject"] == "Teste"
        assert parsed["To"] == "eu@example.com"

    def test_still_validates_the_message(self, cli: Harness) -> None:
        assert cli("--dry-run", "--to", "invalido") == ExitCode.USAGE_ERROR


class TestErrors:
    def test_missing_sender(self, cli: Harness) -> None:
        assert cli(env={"EMAILME_PASSWORD": "pw"}) == ExitCode.CONFIG_ERROR
        assert "--from" in cli.stderr.getvalue()

    def test_missing_password(self, cli: Harness) -> None:
        assert cli(env={"EMAILME_USERNAME": "eu@example.com"}) == ExitCode.CONFIG_ERROR
        assert "EMAILME_PASSWORD" in cli.stderr.getvalue()
        assert cli.sent == []

    def test_invalid_recipient(self, cli: Harness) -> None:
        assert cli("--to", "sem-arroba") == ExitCode.USAGE_ERROR
        assert "invalid email address" in cli.stderr.getvalue()

    def test_delivery_failure(self, cli: Harness) -> None:
        class Rejecting:
            def send(self, message: EmailMessage) -> None:
                raise AuthenticationError("credenciais recusadas")

        code = main(
            [],
            env=BASE_ENV,
            transport_factory=lambda _: Rejecting(),
            stdout=cli.stdout,
            stderr=cli.stderr,
        )
        assert code == ExitCode.DELIVERY_ERROR
        assert "credenciais recusadas" in cli.stderr.getvalue()

    def test_unknown_flag_exits_with_usage_error(self, cli: Harness) -> None:
        with pytest.raises(SystemExit) as info:
            cli("--nao-existe")
        assert info.value.code == ExitCode.USAGE_ERROR


class TestParser:
    def test_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as info:
            build_parser().parse_args(["--version"])
        assert info.value.code == 0
        assert emailme.__version__ in capsys.readouterr().out

    def test_defaults(self) -> None:
        args = build_parser().parse_args([])
        assert args.body == "Hello"
        assert args.recipients is None
        assert args.dry_run is False
