"""Strip and block identifying data before persisting extracted statement facts.

Policy: only non-identifying financial fields may be stored. Full document text,
names, addresses, government IDs (especially SSN), and similar fields must not
be persisted. All string values pass through pattern redaction as defense in depth.
"""

from __future__ import annotations

import copy
import re
from typing import Any

REDACTION_TOKEN = "[REDACTED]"

# Keys must never appear in persisted JSON (case-insensitive match on leaf keys).
BLOCKED_LEAF_KEYS: frozenset[str] = frozenset(
    {
        "ssn",
        "social_security_number",
        "social_security_no",
        "social_security",
        "taxpayer_ssn",
        "spouse_ssn",
        "itin",
        "itin_number",
        "drivers_license",
        "drivers_license_number",
        "passport",
        "passport_number",
        "date_of_birth",
        "dob",
        "phone",
        "phone_number",
        "email",
        "address",
        "street",
        "city",
        "zip",
        "zip_code",
        "full_name",
        "taxpayer_name",
        "spouse_name",
        "employer_name",
        "employer_identification",
        "employer_ein",
        "account_number",
        "bank_account",
        "routing_number",
        "raw_text",
        "full_text",
        "ocr_text",
        "transcript",
    }
)

# US SSN and common variants (including ITIN-style 9xx-xx-xxxx).
_SSN_LIKE = re.compile(
    r"\b(?:\d{3}-\d{2}-\d{4}|\d{3}\s+\d{2}\s+\d{4}|9\d{2}-\d{2}-\d{4})\b"
)


def redact_ssn_patterns(text: str) -> str:
    """Replace SSN/ITIN-shaped patterns in a string."""
    if not text:
        return text
    return _SSN_LIKE.sub(REDACTION_TOKEN, text)


def _blocked_key(name: str) -> bool:
    return name.lower() in BLOCKED_LEAF_KEYS


def drop_blocked_keys(obj: Any) -> Any:
    """Remove subtrees whose dict key is in BLOCKED_LEAF_KEYS (recursive)."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if isinstance(k, str) and _blocked_key(k):
                continue
            out[k] = drop_blocked_keys(v)
        return out
    if isinstance(obj, list):
        return [drop_blocked_keys(x) for x in obj]
    return obj


def redact_strings_deep(obj: Any) -> Any:
    """Apply SSN-pattern redaction to every string (recursive)."""
    if isinstance(obj, str):
        return redact_ssn_patterns(obj)
    if isinstance(obj, dict):
        return {k: redact_strings_deep(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_strings_deep(x) for x in obj]
    return obj


def residual_ssn_like_patterns(text: str) -> bool:
    """True if any SSN-shaped sequence remains after basic redaction."""
    if not text:
        return False
    scrubbed = redact_ssn_patterns(text)
    return bool(_SSN_LIKE.search(scrubbed))


def prepare_financial_facts_for_persistence(facts: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy safe to store: blocked keys removed, strings redacted.

    Raises ValueError if a numeric-looking id sequence still matches SSN patterns
    after redaction (fail closed).
    """
    cleaned = drop_blocked_keys(copy.deepcopy(facts))
    cleaned = redact_strings_deep(cleaned)

    def _scan(o: Any) -> None:
        if isinstance(o, str):
            if residual_ssn_like_patterns(o):
                raise ValueError(
                    "Refusing to persist: residual SSN-like pattern after redaction"
                )
        elif isinstance(o, dict):
            for v in o.values():
                _scan(v)
        elif isinstance(o, list):
            for x in o:
                _scan(x)

    _scan(cleaned)
    return cleaned
