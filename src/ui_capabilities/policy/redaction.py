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
    """Redacts by sensitive key names, secret patterns, and registered
    concrete sensitive values (e.g. bound invocation inputs, extracted
    sensitive outputs)."""

    def __init__(self, extra_sensitive_keys: tuple[str, ...] = ()):
        self._key_parts = tuple(k.lower() for k in SENSITIVE_KEY_PARTS + extra_sensitive_keys)
        self._sensitive_values: list[str] = []

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
