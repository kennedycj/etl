"""Privacy redaction for persisted statement facts."""

import pytest

from finance_app.statements.redaction import (
    prepare_financial_facts_for_persistence,
    redact_ssn_patterns,
)


def test_redact_ssn_dashed():
    assert "123-45-6789" not in redact_ssn_patterns("ID 123-45-6789 end")
    assert "[REDACTED]" in redact_ssn_patterns("ID 123-45-6789 end")


def test_redact_ssn_spaced():
    s = redact_ssn_patterns("SSN 123 45 6789")
    assert "[REDACTED]" in s


def test_drop_blocked_keys():
    raw = {
        "adjusted_gross_income": 125000,
        "ssn": "123-45-6789",
        "nested": {"email": "x@y.com"},
    }
    out = prepare_financial_facts_for_persistence(raw)
    assert out["adjusted_gross_income"] == 125000
    assert "ssn" not in out
    assert "email" not in str(out)


def test_ssn_in_freeform_string_is_redacted_not_preserved():
    facts = {"memo": "see 987-65-4321 below"}
    out = prepare_financial_facts_for_persistence(facts)
    assert "987-65-4321" not in str(out)
    assert "[REDACTED]" in str(out)
