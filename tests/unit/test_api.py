import os
from email.message import EmailMessage
from pathlib import Path
from typing import ClassVar

import pytest

import emailme
from emailme import api
from emailme.api import email_me, load_environment
from emailme.config import SmtpSettings
from emailme.errors import ConfigurationError
from emailme.transport import InMemoryTransport


class RecordingSmtpTransport:
    """Substitui ``SmtpTransport`` para capturar as configurações construídas."""

    created: ClassVar[list[RecordingSmtpTransport]] = []

    def __init__(self, settings: SmtpSettings) -> None:
        self.settings = settings
        self.outbox: list[EmailMessage] = []
        type(self).created.append(self)

    def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)


@pytest.fixture
def recording_smtp(monkeypatch: pytest.MonkeyPatch) -> type[RecordingSmtpTransport]:
    RecordingSmtpTransport.created = []
    monkeypatch.setattr(api, "SmtpTransport", RecordingSmtpTransport)
    return RecordingSmtpTransport


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Diretório de trabalho vazio e ambiente sem variáveis do emailme."""
    for key in list(os.environ):
        if key.startswith("EMAILME_") or key == "SENHA_DE_APP_GMAIL":
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestEmailMe:
    def test_is_exported_at_package_level(self) -> None:
        assert emailme.email_me is email_me

    def test_sends_to_self_through_given_transport(self) -> None:
        transport = InMemoryTransport()
        email = email_me("eu@example.com", "Assunto", "Corpo", transport=transport)

        [sent] = transport.outbox
        assert sent["From"] == sent["To"] == "eu@example.com"
        assert sent["Subject"] == "Assunto"
        assert email.body == "Corpo"

    def test_uses_defaults_like_the_original_function(self) -> None:
        transport = InMemoryTransport()
        email = email_me("eu@example.com", transport=transport)
        assert (email.subject, email.body) == ("Automatic Email via Python", "Hello")

    def test_builds_smtp_transport_from_env_mapping(
        self, recording_smtp: type[RecordingSmtpTransport]
    ) -> None:
        email_me("eu@example.com", env={"SENHA_DE_APP_GMAIL": "pw"})

        [transport] = recording_smtp.created
        assert transport.settings == SmtpSettings(username="eu@example.com", password="pw")
        assert len(transport.outbox) == 1

    def test_reads_dotenv_from_current_directory(
        self, clean_env: Path, recording_smtp: type[RecordingSmtpTransport]
    ) -> None:
        (clean_env / ".env").write_text("SENHA_DE_APP_GMAIL=from-file\n")
        email_me("eu@example.com")
        assert recording_smtp.created[0].settings.password == "from-file"

    def test_missing_password_raises_environment_error(self, clean_env: Path) -> None:
        with pytest.raises(EnvironmentError, match="SENHA_DE_APP_GMAIL"):
            email_me("eu@example.com")

    def test_missing_password_raises_configuration_error(self) -> None:
        with pytest.raises(ConfigurationError):
            email_me("eu@example.com", env={})


class TestLoadEnvironment:
    def test_merges_dotenv_file_with_process_environment(
        self, clean_env: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (clean_env / ".env").write_text("EMAILME_PASSWORD=file\nEMAILME_SMTP_HOST=file-host\n")
        monkeypatch.setenv("EMAILME_SMTP_HOST", "env-host")

        env = load_environment()

        assert env["EMAILME_PASSWORD"] == "file"
        assert env["EMAILME_SMTP_HOST"] == "env-host"  # o ambiente tem precedência

    def test_does_not_mutate_os_environ(self, clean_env: Path) -> None:
        (clean_env / ".env").write_text("EMAILME_PASSWORD=file\n")
        load_environment()
        assert "EMAILME_PASSWORD" not in os.environ

    def test_accepts_explicit_path(self, clean_env: Path) -> None:
        custom = clean_env / "config" / "custom.env"
        custom.parent.mkdir()
        custom.write_text("EMAILME_USERNAME=custom@example.com\n")
        assert load_environment(custom)["EMAILME_USERNAME"] == "custom@example.com"

    def test_ignores_valueless_entries(self, clean_env: Path) -> None:
        (clean_env / ".env").write_text("EMAILME_FLAG\n")
        assert "EMAILME_FLAG" not in load_environment()

    def test_works_without_dotenv_file(self, clean_env: Path) -> None:
        assert load_environment() == dict(os.environ)
