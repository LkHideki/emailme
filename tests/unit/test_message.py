import dataclasses
from email import message_from_bytes, policy

import pytest

from emailme.errors import InvalidEmailError
from emailme.message import DEFAULT_BODY, DEFAULT_SUBJECT, Email, validate_address


class TestValidateAddress:
    @pytest.mark.parametrize(
        "address",
        ["eu@example.com", "first.last+tag@sub.example.com.br", "a@b", "user_name-1@x.io"],
    )
    def test_accepts_valid_addresses(self, address: str) -> None:
        assert validate_address(address) == address

    def test_strips_surrounding_whitespace(self) -> None:
        assert validate_address("  eu@example.com\t") == "eu@example.com"

    @pytest.mark.parametrize(
        "address",
        [
            "",
            "   ",
            "sem-arroba",
            "@example.com",
            "eu@",
            "eu @example.com",
            "Fulano <eu@example.com>",
            "eu@example.com\nBcc: vitima@example.com",
            "eu@example.com\r",
        ],
    )
    def test_rejects_invalid_addresses(self, address: str) -> None:
        with pytest.raises(InvalidEmailError):
            validate_address(address)


class TestEmail:
    def test_create_defaults_to_sending_to_self(self) -> None:
        email = Email.create(sender="eu@example.com")
        assert email.recipients == ("eu@example.com",)
        assert email.subject == DEFAULT_SUBJECT
        assert email.body == DEFAULT_BODY

    def test_create_normalizes_and_deduplicates_recipients_keeping_order(self) -> None:
        email = Email.create(
            sender=" eu@example.com ",
            recipients=["b@example.com", " a@example.com", "b@example.com"],
        )
        assert email.sender == "eu@example.com"
        assert email.recipients == ("b@example.com", "a@example.com")

    def test_requires_at_least_one_recipient(self) -> None:
        with pytest.raises(InvalidEmailError, match="recipient"):
            Email.create(sender="eu@example.com", recipients=[])

    def test_direct_construction_is_validated(self) -> None:
        with pytest.raises(InvalidEmailError):
            Email(sender="eu@example.com", recipients=("invalido",))

    @pytest.mark.parametrize("subject", ["a\nBcc: x@y.com", "a\r\nb", "\r"])
    def test_rejects_header_injection_in_subject(self, subject: str) -> None:
        with pytest.raises(InvalidEmailError, match="subject"):
            Email.create(sender="eu@example.com", subject=subject)

    def test_is_immutable(self) -> None:
        email = Email.create(sender="eu@example.com")
        with pytest.raises(dataclasses.FrozenInstanceError):
            email.subject = "outro"  # type: ignore[misc]

    def test_is_invalid_email_error_also_a_value_error(self) -> None:
        with pytest.raises(ValueError):  # noqa: PT011
            Email.create(sender="x")


class TestToMime:
    def test_sets_headers(self) -> None:
        mime = Email.create(
            sender="eu@example.com",
            recipients=["a@example.com", "b@example.com"],
            subject="Relatório",
        ).to_mime()
        assert mime["From"] == "eu@example.com"
        assert mime["To"] == "a@example.com, b@example.com"
        assert mime["Subject"] == "Relatório"

    def test_body_is_utf8_plain_text(self) -> None:
        mime = Email.create(sender="eu@example.com", body="Olá, açaí! ✉️").to_mime()
        assert mime.get_content_type() == "text/plain"
        assert mime.get_content_charset() == "utf-8"
        assert mime.get_content() == "Olá, açaí! ✉️\n"

    def test_survives_serialization_roundtrip(self) -> None:
        original = Email.create(sender="eu@example.com", subject="Ção", body="linha 1\nlinha 2")
        parsed = message_from_bytes(original.to_mime().as_bytes(), policy=policy.default)
        assert parsed["Subject"] == "Ção"
        assert parsed.get_content() == "linha 1\nlinha 2\n"
