import pytest

from emailme.config import DEFAULT_HOST, DEFAULT_PORT, DEFAULT_TIMEOUT, SmtpSettings
from emailme.errors import ConfigurationError, EmailMeError


def make(**overrides: object) -> SmtpSettings:
    params: dict[str, object] = {"username": "eu@example.com", "password": "secret"} | overrides
    return SmtpSettings(**params)  # type: ignore[arg-type]


class TestSmtpSettings:
    def test_defaults_point_to_gmail(self) -> None:
        settings = make()
        assert settings.host == DEFAULT_HOST == "smtp.gmail.com"
        assert settings.port == DEFAULT_PORT == 587
        assert settings.use_starttls is True
        assert settings.timeout == DEFAULT_TIMEOUT

    def test_password_is_hidden_from_repr(self) -> None:
        assert "secret" not in repr(make())

    def test_is_immutable(self) -> None:
        settings = make()
        with pytest.raises(AttributeError):
            settings.port = 25  # type: ignore[misc]

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("username", ""),
            ("username", "   "),
            ("password", ""),
            ("host", ""),
            ("port", 0),
            ("port", 65536),
            ("port", -1),
            ("timeout", 0),
            ("timeout", -1.5),
        ],
    )
    def test_rejects_invalid_values(self, field: str, value: object) -> None:
        with pytest.raises(ConfigurationError):
            make(**{field: value})


class TestFromEnv:
    def test_reads_all_variables(self) -> None:
        env = {
            "EMAILME_USERNAME": "eu@example.com",
            "EMAILME_PASSWORD": "pw",
            "EMAILME_SMTP_HOST": "smtp.example.com",
            "EMAILME_SMTP_PORT": "2525",
            "EMAILME_STARTTLS": "no",
            "EMAILME_TIMEOUT": "2.5",
        }
        assert SmtpSettings.from_env(env) == SmtpSettings(
            username="eu@example.com",
            password="pw",
            host="smtp.example.com",
            port=2525,
            use_starttls=False,
            timeout=2.5,
        )

    def test_uses_defaults_for_missing_optional_variables(self) -> None:
        settings = SmtpSettings.from_env({"EMAILME_PASSWORD": "pw"}, username="eu@example.com")
        assert settings == make(password="pw")

    def test_blank_optional_variables_fall_back_to_defaults(self) -> None:
        env = {"EMAILME_PASSWORD": "pw", "EMAILME_SMTP_PORT": " ", "EMAILME_TIMEOUT": ""}
        settings = SmtpSettings.from_env(env, username="eu@example.com")
        assert (settings.port, settings.timeout) == (DEFAULT_PORT, DEFAULT_TIMEOUT)

    def test_supports_legacy_password_variable(self) -> None:
        settings = SmtpSettings.from_env({"SENHA_DE_APP_GMAIL": "legacy"}, username="a@b.com")
        assert settings.password == "legacy"

    def test_new_password_variable_wins_over_legacy(self) -> None:
        env = {"SENHA_DE_APP_GMAIL": "legacy", "EMAILME_PASSWORD": "new"}
        assert SmtpSettings.from_env(env, username="a@b.com").password == "new"

    def test_explicit_username_wins_over_environment(self) -> None:
        env = {"EMAILME_USERNAME": "env@example.com", "EMAILME_PASSWORD": "pw"}
        assert SmtpSettings.from_env(env, username="arg@example.com").username == "arg@example.com"

    def test_missing_username(self) -> None:
        with pytest.raises(ConfigurationError, match="EMAILME_USERNAME"):
            SmtpSettings.from_env({"EMAILME_PASSWORD": "pw"})

    def test_missing_password_is_backwards_compatible_environment_error(self) -> None:
        with pytest.raises(EnvironmentError, match="SENHA_DE_APP_GMAIL") as info:
            SmtpSettings.from_env({}, username="a@b.com")
        assert isinstance(info.value, ConfigurationError)
        assert isinstance(info.value, EmailMeError)

    @pytest.mark.parametrize(
        ("key", "value", "message"),
        [
            ("EMAILME_SMTP_PORT", "abc", "EMAILME_SMTP_PORT must be an integer"),
            ("EMAILME_SMTP_PORT", "70000", "port out of range"),
            ("EMAILME_TIMEOUT", "fast", "EMAILME_TIMEOUT must be a number"),
            ("EMAILME_STARTTLS", "maybe", "EMAILME_STARTTLS must be a boolean"),
        ],
    )
    def test_rejects_malformed_values(self, key: str, value: str, message: str) -> None:
        env = {"EMAILME_PASSWORD": "pw", key: value}
        with pytest.raises(ConfigurationError, match=message):
            SmtpSettings.from_env(env, username="a@b.com")

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1", True),
            ("true", True),
            ("TRUE", True),
            (" yes ", True),
            ("on", True),
            ("sim", True),
            ("0", False),
            ("False", False),
            ("no", False),
            ("off", False),
            ("não", False),
        ],
    )
    def test_boolean_parsing(self, raw: str, expected: bool) -> None:
        env = {"EMAILME_PASSWORD": "pw", "EMAILME_STARTTLS": raw}
        assert SmtpSettings.from_env(env, username="a@b.com").use_starttls is expected
