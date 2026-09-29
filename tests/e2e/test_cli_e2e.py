"""Testes ponta a ponta: executam a CLI instalada em um processo separado."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import LocalSmtpServer

CONSOLE_SCRIPT = Path(sys.executable).parent / "emailme"


def _clean_environ(**extra: str) -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("EMAILME_") and k != "SENHA_DE_APP_GMAIL"
    }
    return env | extra


@pytest.fixture(params=["module", "console-script"])
def command(request: pytest.FixtureRequest) -> list[str]:
    """A CLI pode ser chamada via ``python -m emailme`` ou pelo script instalado."""
    if request.param == "module":
        return [sys.executable, "-m", "emailme"]
    if not CONSOLE_SCRIPT.exists():  # pragma: no cover
        pytest.skip("console script not installed")
    return [str(CONSOLE_SCRIPT)]


def run(
    command: list[str],
    *args: str,
    env: dict[str, str],
    cwd: Path,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*command, *args],
        env=_clean_environ(**env),
        cwd=cwd,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_sends_email_to_self(
    command: list[str], smtp_server: LocalSmtpServer, tmp_path: Path
) -> None:
    result = run(command, "Corpo", "-s", "Assunto", env=smtp_server.env(), cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert "sucesso" in result.stdout
    [received] = smtp_server.messages
    assert received.rcpt_tos == [smtp_server.username]
    message = received.parse()
    assert message["Subject"] == "Assunto"
    assert message.get_content() == "Corpo\n"


def test_reads_body_from_stdin_and_sends_to_many(
    command: list[str], smtp_server: LocalSmtpServer, tmp_path: Path
) -> None:
    result = run(
        command,
        "-",
        "--to",
        "a@example.com",
        "--to",
        "b@example.com",
        env=smtp_server.env(),
        cwd=tmp_path,
        stdin="saída de outro comando ✅\n",
    )

    assert result.returncode == 0, result.stderr
    [received] = smtp_server.messages
    assert received.rcpt_tos == ["a@example.com", "b@example.com"]
    assert received.parse().get_content() == "saída de outro comando ✅\n"


def test_configuration_from_dotenv_file_in_cwd(
    command: list[str], smtp_server: LocalSmtpServer, tmp_path: Path
) -> None:
    dotenv = "\n".join(f"{k}={v}" for k, v in smtp_server.env().items())
    (tmp_path / ".env").write_text(dotenv, encoding="utf-8")

    result = run(command, "via .env", env={}, cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    assert len(smtp_server.messages) == 1


def test_verbose_logs_to_stderr(
    command: list[str], smtp_server: LocalSmtpServer, tmp_path: Path
) -> None:
    result = run(command, "-v", env=smtp_server.env(), cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "INFO emailme.service" in result.stderr


def test_dry_run_does_not_contact_server(command: list[str], tmp_path: Path) -> None:
    result = run(
        command,
        "Corpo",
        "--dry-run",
        env={"EMAILME_USERNAME": "eu@example.com"},
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    assert "Subject: Automatic Email via Python" in result.stdout
    assert "To: eu@example.com" in result.stdout


def test_wrong_password_exits_with_delivery_error(
    command: list[str], smtp_server: LocalSmtpServer, tmp_path: Path
) -> None:
    result = run(command, env=smtp_server.env(EMAILME_PASSWORD="errada"), cwd=tmp_path)
    assert result.returncode == 1
    assert "rejected the credentials" in result.stderr
    assert "Traceback" not in result.stderr
    assert smtp_server.messages == []


def test_missing_password_exits_with_config_error(command: list[str], tmp_path: Path) -> None:
    result = run(command, env={"EMAILME_USERNAME": "eu@example.com"}, cwd=tmp_path)
    assert result.returncode == 3
    assert "EMAILME_PASSWORD" in result.stderr


def test_help(command: list[str], tmp_path: Path) -> None:
    result = run(command, "--help", env={}, cwd=tmp_path)
    assert result.returncode == 0
    assert "usage: emailme" in result.stdout
