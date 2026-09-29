import pytest
from hypothesis import given
from hypothesis import strategies as st

from emailme.config import SmtpSettings
from emailme.errors import ConfigurationError

BASE = {"EMAILME_USERNAME": "eu@example.com", "EMAILME_PASSWORD": "pw"}


@given(st.integers(min_value=1, max_value=65535))
def test_any_valid_port_roundtrips_through_environment(port: int) -> None:
    assert SmtpSettings.from_env(BASE | {"EMAILME_SMTP_PORT": str(port)}).port == port


@given(st.one_of(st.integers(max_value=0), st.integers(min_value=65536)))
def test_ports_outside_range_are_rejected(port: int) -> None:
    with pytest.raises(ConfigurationError):
        SmtpSettings.from_env(BASE | {"EMAILME_SMTP_PORT": str(port)})


@given(st.sampled_from(["1", "true", "yes", "on", "sim"]), st.data())
def test_true_tokens_are_case_insensitive(token: str, data: st.DataObject) -> None:
    mixed = "".join(c.upper() if data.draw(st.booleans(), label=f"upper {c}") else c for c in token)
    assert SmtpSettings.from_env(BASE | {"EMAILME_STARTTLS": mixed}).use_starttls is True


@given(st.floats(min_value=1e-3, max_value=1e6, allow_nan=False, allow_infinity=False))
def test_positive_timeouts_are_accepted(timeout: float) -> None:
    assert SmtpSettings.from_env(BASE | {"EMAILME_TIMEOUT": repr(timeout)}).timeout == timeout


@given(st.text(min_size=1))
def test_password_never_leaks_into_repr(password: str) -> None:
    settings = SmtpSettings(username="eu@example.com", password=password)
    assert f"password={password!r}" not in repr(settings)
