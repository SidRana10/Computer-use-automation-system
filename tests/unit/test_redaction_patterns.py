"""Durable evidence must not carry data the run never supplied.

The Phase-1 redactor scrubs registered runtime values (bound inputs, extracted
outputs). A live target also renders values the run never touched: a session id
in the status bar of every page, a per-session transaction token in a hidden
field, and other members' contact details. Those reach evidence through page
text and DOM snapshots, so a target profile declares patterns for them.
"""

from ui_capabilities.policy.redaction import REDACTED, Redactor
from ui_capabilities.targets import get_profile

MERIDIAN_PATTERNS = get_profile("meridian").redaction_text_patterns

FOOTER = "OPR TELLER1  |  BR MAIN-001  |  09/05/2026 11:21:42  |  SID C47B2CFC"
TOKEN_HTML = '<input type="hidden" name="_token" value="2e3b8154-351">'
RECORD = "Name: Lovelace, Ada E-mail: replay-verify@example.com Phone: 555-0155"


def _redactor() -> Redactor:
    return Redactor(text_patterns=MERIDIAN_PATTERNS)


def test_session_identifier_and_operator_are_scrubbed():
    """The status bar carries both a live session id and the signed-on operator.

    The operator is rendered uppercase, so registering the bound input value
    ("teller1") does not cover it — a pattern is required.
    """
    out = _redactor().redact_text(FOOTER)
    assert "C47B2CFC" not in out
    assert "TELLER1" not in out
    assert REDACTED in out
    assert "BR MAIN-001" in out, "non-identifying operational context should survive"
    assert "09/05/2026" in out, "timestamps stay so evidence remains orderable"


def test_hidden_transaction_token_is_scrubbed_from_dom():
    out = _redactor().redact_text(TOKEN_HTML)
    assert "2e3b8154-351" not in out
    assert 'name="_token"' in out, "markup structure stays readable"
    assert REDACTED in out


def test_member_contact_details_are_scrubbed():
    out = _redactor().redact_text(RECORD)
    assert "replay-verify@example.com" not in out
    assert "555-0155" not in out


def test_patterns_apply_through_the_structured_log_path():
    """redact() walks nested structures via redact_text, so logs are covered."""
    payload = {"observed": FOOTER, "nested": [{"html": TOKEN_HTML}]}
    out = _redactor().redact(payload)
    assert "C47B2CFC" not in str(out)
    assert "2e3b8154-351" not in str(out)


def test_registered_runtime_values_still_work():
    redactor = _redactor()
    redactor.register_sensitive_value("100234")
    assert "100234" not in redactor.redact_text("member 100234 selected")


def test_northstar_redaction_is_unchanged():
    """A profile with no declared patterns behaves exactly as in Phase 1."""
    assert get_profile("northstar").redaction_text_patterns == ()
    plain = Redactor()
    assert plain.redact_text(FOOTER) == FOOTER
    assert plain.redact_text("sk-ant-abc123") == REDACTED


def test_secret_patterns_are_not_weakened():
    redactor = _redactor()
    assert redactor.redact_text("Authorization: Bearer abc.def") == REDACTED
    assert "sk-ant-" not in redactor.redact_text("key sk-ant-secret123")
