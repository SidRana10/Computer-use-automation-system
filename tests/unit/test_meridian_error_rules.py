"""MERIDIAN error-rule text matching, pinned against page text captured live.

Every string below is the exact text observed on the real target during P2
reconnaissance (both the six `?inject=` fault-injection states and natural
business outcomes), not an assumption. `meridian_error_rules()` had no direct
unit coverage before this — only reached indirectly through the sign-on
integration tests — so a wrong or drifted string here would have gone
undetected until a live replay run happened to hit it.
"""

from __future__ import annotations

import pytest

from tests.fixtures.fakes import FakeSurface
from ui_capabilities.models.errors import ErrorClassification
from ui_capabilities.replay.error_classifier import classify_current_state
from ui_capabilities.targets.meridian import meridian_error_rules

ENTRY = "https://web-sample.interface-hiring.com/"


class _Artifact:
    """classify_current_state only reads `.error_rules`; avoid building a full
    CapabilityArtifact for every case."""

    def __init__(self, rules):
        self.error_rules = rules


@pytest.fixture
def artifact():
    return _Artifact(meridian_error_rules())


async def _classify(page_text: str, artifact):
    surface = FakeSurface("/tmp", page_text=page_text, url=ENTRY)
    return await classify_current_state(surface, artifact)


# ---------------------------------------------------- six injected states


async def test_inject_validation_maps_to_transaction_rejected(artifact):
    rule = await _classify(
        "TRANSACTION REJECTED The transaction could not be completed as entered. "
        "Please review the field values and resubmit.",
        artifact,
    )
    assert rule.code == "VALIDATION_REJECTED"
    assert rule.classification == ErrorClassification.BUSINESS_OUTCOME


async def test_inject_notfound_maps_to_member_not_found(artifact):
    rule = await _classify(
        "RECORD NOT FOUND The requested member record could not be located on this host.",
        artifact,
    )
    assert rule.code == "MEMBER_NOT_FOUND"
    assert rule.classification == ErrorClassification.BUSINESS_OUTCOME


async def test_inject_permission_maps_to_supervisor_required(artifact):
    rule = await _classify(
        "SUPERVISOR OVERRIDE REQUIRED Operator profile teller1 is not authorized to perform "
        "this function. A supervisor must sign on to complete this request.",
        artifact,
    )
    assert rule.code == "SUPERVISOR_REQUIRED"
    assert rule.classification == ErrorClassification.HARD_FAILURE


async def test_inject_timeout_maps_to_session_expired(artifact):
    rule = await _classify(
        "YOUR SESSION HAS TIMED OUT For security, your session ended due to inactivity.",
        artifact,
    )
    assert rule.code == "SESSION_EXPIRED"
    assert rule.classification == ErrorClassification.HARD_FAILURE


async def test_inject_maintenance_maps_to_recoverable_maintenance_window(artifact):
    rule = await _classify(
        "SCHEDULED MAINTENANCE IN PROGRESS The host is temporarily unavailable while nightly "
        "batch posting completes.",
        artifact,
    )
    assert rule.code == "MAINTENANCE_WINDOW"
    assert rule.classification == ErrorClassification.RECOVERABLE
    assert [a.kind for a in rule.recovery] == ["wait", "reload"]
    assert rule.max_attempts == 2


async def test_inject_server_maps_to_application_error(artifact):
    rule = await _classify(
        "APPLICATION ERROR An unexpected error occurred while processing your request. "
        "Reference: ERR-C97FAA1B",
        artifact,
    )
    assert rule.code == "APPLICATION_ERROR"
    assert rule.classification == ErrorClassification.HARD_FAILURE


# --------------------------------------------------- natural business outcomes


async def test_bad_login_is_business_outcome(artifact):
    rule = await _classify("Invalid operator ID or password.", artifact)
    assert rule.code == "BAD_LOGIN"
    assert rule.classification == ErrorClassification.BUSINESS_OUTCOME


async def test_no_search_results_is_business_outcome(artifact):
    rule = await _classify("No member records matched your search.", artifact)
    assert rule.code == "NO_SEARCH_RESULTS"
    assert rule.classification == ErrorClassification.BUSINESS_OUTCOME


async def test_insufficient_funds_maps_to_transaction_could_not_be_validated(artifact):
    """Distinct from the injected VALIDATION_REJECTED text: this is the
    transfer form's own pre-review rejection (never reaches a live POST)."""
    rule = await _classify(
        "FUNDS TRANSFER The transaction could not be validated: "
        "Insufficient available balance in the source share.",
        artifact,
    )
    assert rule.code == "TRANSACTION_REJECTED"
    assert rule.classification == ErrorClassification.BUSINESS_OUTCOME


async def test_open_share_below_minimum_deposit_is_business_outcome(artifact):
    """Found live testing meridian.open_share: a Certificate opened below its
    $500 minimum renders "The request could not be validated:" — distinct
    wording from TRANSACTION_REJECTED's "transaction" phrasing, so it did not
    match any existing rule and fell through to an unclassified hard failure
    until this rule was added."""
    rule = await _classify(
        "OPEN NEW SHARE The request could not be validated: "
        "Certificates require a minimum opening deposit of $500.00.",
        artifact,
    )
    assert rule.code == "OPEN_SHARE_VALIDATION_FAILED"
    assert rule.classification == ErrorClassification.BUSINESS_OUTCOME


async def test_invalid_email_maps_to_field_validation_failed(artifact):
    rule = await _classify(
        "UPDATE MEMBER INFORMATION Please correct the following: E-mail address is not in a valid format.",
        artifact,
    )
    assert rule.code == "FIELD_VALIDATION_FAILED"
    assert rule.classification == ErrorClassification.BUSINESS_OUTCOME


async def test_teller_attempting_supervisor_hold_maps_to_supervisor_required(artifact):
    """The same SUPERVISOR_REQUIRED text a teller sees after clicking Continue
    on the Place Account Hold form (not just the ?inject=permission page)."""
    rule = await _classify(
        "Operator profile teller1 is not authorized to perform this function. "
        "A supervisor must sign on to complete this request.",
        artifact,
    )
    assert rule.code == "SUPERVISOR_REQUIRED"


# ----------------------------------------------------------- fail closed


async def test_unrecognized_state_matches_no_rule(artifact):
    """An unknown/unrecognized page must never be silently classified —
    `classify_current_state` returning None is what makes replay fall through
    to an unclassified hard failure rather than guessing."""
    rule = await _classify("Something entirely unexpected that no rule describes.", artifact)
    assert rule is None


async def test_rule_order_is_most_specific_first_for_overlapping_text():
    """MEMBER_NOT_FOUND's text is a substring-free match, but the rule list
    order still matters for any future overlapping addition; pin that the
    factory returns rules in a stable, deliberate order rather than an
    incidental one."""
    rules = meridian_error_rules()
    codes = [r.code for r in rules]
    assert codes.index("BAD_LOGIN") < codes.index("APPLICATION_ERROR")
    assert len(codes) == len(set(codes)), "rule codes must be unique"
