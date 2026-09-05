"""One central Redactor used by loggers, evidence metadata, error
observations, and human-action capture. Nothing else implements redaction."""

from __future__ import annotations

import re
from typing import Any

REDACTED = "[REDACTED]"

# Case-insensitive substring match on dictionary keys.
SENSITIVE_KEY_PARTS = (
    "member_id",
    "account_number",
    "password",
    "passwd",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "secret",
    "ssn",
    "cookie",
    "session_id",
    "credential",
)

# Secret-shaped string patterns scrubbed from any logged text.
SECRET_PATTERNS = [
    re.compile(r"sk-ant-[A-Za-z0-9_\-]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)authorization:\s*\S+"),
]


class Redactor:
    """Redacts by sensitive key names, secret patterns, registered concrete
    sensitive values (bound invocation inputs, extracted outputs), and
    target-declared text patterns.

    Registered values only cover data the run itself supplied or read. A live
    target also renders data the run never touches — session identifiers,
    per-transaction tokens, other members' contact details and balances — and
    those reach durable evidence through page text and DOM snapshots. A target
    profile declares patterns for that class; without them the registered-value
    mechanism alone is not sufficient.
    """

    def __init__(
        self,
        extra_sensitive_keys: tuple[str, ...] = (),
        text_patterns: tuple[str | re.Pattern[str], ...] = (),
    ):
        self._key_parts = tuple(k.lower() for k in SENSITIVE_KEY_PARTS + extra_sensitive_keys)
        self._sensitive_values: list[str] = []
        self._text_patterns: list[re.Pattern[str]] = [
            pat if isinstance(pat, re.Pattern) else re.compile(pat) for pat in text_patterns
        ]

    def register_sensitive_value(self, value: Any) -> None:
        """Register a concrete runtime value (never persisted) so any string
        containing it gets scrubbed."""
        text = str(value)
        if text and len(text) >= 3 and text not in self._sensitive_values:
            self._sensitive_values.append(text)

    def is_sensitive_key(self, key: str) -> bool:
        lowered = key.lower()
        return any(part in lowered for part in self._key_parts)

    def redact_text(self, text: str) -> str:
        for pattern in SECRET_PATTERNS:
            text = pattern.sub(REDACTED, text)
        for pattern in self._text_patterns:
            text = pattern.sub(_keep_group_prefix, text)
        for value in self._sensitive_values:
            if value in text:
                text = text.replace(value, REDACTED)
        return text

    def redact(self, obj: Any) -> Any:
        """Recursively redact a JSON-ish structure."""
        if isinstance(obj, dict):
            return {
                k: (REDACTED if self.is_sensitive_key(str(k)) and obj[k] not in (None, "") else self.redact(v))
                for k, v in obj.items()
            }
        if isinstance(obj, (list, tuple)):
            return [self.redact(v) for v in obj]
        if isinstance(obj, str):
            return self.redact_text(obj)
        return obj


def _keep_group_prefix(match: re.Match[str]) -> str:
    """Replace a pattern match with the redaction marker.

    A pattern may capture a leading group it wants preserved (e.g. the literal
    `value="` of a hidden token field) so the surrounding markup stays readable
    while the secret itself is removed.
    """
    if match.groups():
        return f"{match.group(1)}{REDACTED}"
    return REDACTED
