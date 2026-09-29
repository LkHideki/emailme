"""Testes baseados em propriedades: invariantes que valem para *qualquer* entrada."""

from email import message_from_bytes, policy
from email.message import EmailMessage

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from emailme.errors import InvalidEmailError
from emailme.message import Email, validate_address

_ATOM = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-+", min_size=1, max_size=20)
_LABEL = st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789", min_size=1, max_size=15)

addresses = st.builds(
    lambda local, labels: f"{'.'.join(local)}@{'.'.join(labels)}",
    st.lists(_ATOM, min_size=1, max_size=3),
    st.lists(_LABEL, min_size=1, max_size=4),
)

# Qualquer texto unicode sem quebras de linha nem caracteres de controle,
# normalizado quanto a espaços (headers não preservam espaços repetidos).
subjects = st.text(
    alphabet=st.characters(codec="utf-8", categories=["L", "M", "N", "P", "S", "Zs"]),
    max_size=200,
).map(lambda s: " ".join(s.split()))

# Corpo: qualquer texto unicode (sem surrogates), incluindo quebras de linha.
bodies = st.text(
    alphabet=st.characters(codec="utf-8", exclude_characters="\r"),
    max_size=2000,
)


def roundtrip(email: Email) -> EmailMessage:
    return message_from_bytes(email.to_mime().as_bytes(), policy=policy.default)


@given(addresses)
def test_valid_addresses_are_returned_unchanged(address: str) -> None:
    assert validate_address(address) == address


@given(addresses, st.text(alphabet=" \t", max_size=3), st.text(alphabet=" \t", max_size=3))
def test_validation_is_idempotent_and_strips_whitespace(address: str, pre: str, post: str) -> None:
    normalized = validate_address(pre + address + post)
    assert normalized == address
    assert validate_address(normalized) == normalized


@given(st.text(alphabet=st.characters(exclude_characters="@"), max_size=50))
def test_addresses_without_at_sign_are_rejected(text: str) -> None:
    with pytest.raises(InvalidEmailError):
        validate_address(text)


@given(st.text(), st.sampled_from(["\r", "\n", "\r\n"]), st.text())
@example("Assunto", "\n", "Bcc: vitima@example.com")
def test_line_breaks_in_subject_are_always_rejected(before: str, newline: str, after: str) -> None:
    with pytest.raises(InvalidEmailError):
        Email.create(sender="eu@example.com", subject=before + newline + after)


@given(addresses, st.lists(addresses, min_size=1, max_size=5))
def test_recipients_are_unique_and_order_preserving(sender: str, recipients: list[str]) -> None:
    email = Email.create(sender=sender, recipients=recipients)
    assert len(set(email.recipients)) == len(email.recipients)
    assert list(email.recipients) == list(dict.fromkeys(recipients))


@given(sender=addresses, subject=subjects, body=bodies)
@example(sender="a@b.com", subject="Ação ✉️ 日本語", body="From the start\n.\nlinha")
def test_mime_serialization_roundtrip_preserves_content(
    sender: str, subject: str, body: str
) -> None:
    parsed = roundtrip(Email.create(sender=sender, subject=subject, body=body))

    assert parsed["From"] == sender
    assert parsed["Subject"] == subject
    expected_body = body if body.endswith("\n") or not body else body + "\n"
    assert parsed.get_content() == (expected_body or "\n")
