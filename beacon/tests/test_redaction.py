"""Golden set for PII redaction — the privacy control must actually fire."""

from llmobs.redaction import redact


def test_redacts_common_pii_and_counts():
    text = (
        "Email me at jane.doe@example.com or call (415) 555-0132. "
        "SSN 123-45-6789, card 4111 1111 1111 1111, from 10.0.0.42."
    )
    out, counts = redact(text)
    assert "jane.doe@example.com" not in out
    assert "123-45-6789" not in out
    assert "4111 1111 1111 1111" not in out
    assert "10.0.0.42" not in out
    assert "555-0132" not in out
    assert counts.get("email") == 1
    assert counts.get("ssn") == 1
    assert counts.get("credit_card") == 1
    assert "[REDACTED:email]" in out


def test_redacts_api_keys():
    out, counts = redact("token sk-abcdefghijklmnop12345 leaked")
    assert "sk-abcdefghijklmnop12345" not in out
    assert counts.get("api_key") == 1


def test_clean_text_untouched():
    text = "The quick brown fox jumps over the lazy dog."
    out, counts = redact(text)
    assert out == text
    assert counts == {}


def test_empty():
    assert redact("") == ("", {})
