"""The registry names targets; it must not change what Northstar does."""

import pytest

from ui_capabilities.discovery.profiles import demo_app_error_rules
from ui_capabilities.targets import get_profile, profile_names
from ui_capabilities.targets.registry import profile_for_app_id


def test_both_targets_are_registered():
    assert set(profile_names()) == {"northstar", "meridian"}


def test_unknown_profile_fails_loudly():
    with pytest.raises(KeyError, match="unknown target profile"):
        get_profile("nope")


def test_northstar_profile_delegates_to_the_original_phase_one_rules():
    """Phase 1's implementation stays where it was; the profile just names it."""
    profile = get_profile("northstar")
    assert profile.error_rules_factory is demo_app_error_rules
    assert [r.code for r in profile.error_rules_factory()] == [r.code for r in demo_app_error_rules()]
    assert profile.heading_selector == "h2"  # Northstar's <h1> is the app banner


def test_meridian_profile_shape():
    profile = get_profile("meridian")
    assert profile.app_id == "meridian_core"
    assert profile.heading_selector == "h1"
    codes = [r.code for r in profile.error_rules_factory()]
    for expected in (
        "BAD_LOGIN",
        "SUPERVISOR_REQUIRED",
        "SESSION_EXPIRED",
        "MEMBER_NOT_FOUND",
        "NO_SEARCH_RESULTS",
        "TRANSACTION_REJECTED",
        "FIELD_VALIDATION_FAILED",
        "MAINTENANCE_WINDOW",
        "APPLICATION_ERROR",
    ):
        assert expected in codes


def test_profile_lookup_by_app_id():
    assert profile_for_app_id("meridian_core").app_id == "meridian_core"
    assert profile_for_app_id("northstar_member_servicing_demo").heading_selector == "h2"
    assert profile_for_app_id("unknown_app") is None


def test_meridian_fingerprint_markers():
    profile = get_profile("meridian")
    fp = profile.fingerprint(
        "Member Record - Meridian Core",
        "MERIDIAN CORE Member Services Platform v4.2.1 Cornerstone Financial Systems",
    )
    assert fp["app_title"] == "Member Record - Meridian Core"
    assert fp["build_marker"] == "4.2.1"


def test_error_taxonomy_remains_three_way():
    """Escalation is a policy outcome; it must never become a classification."""
    from ui_capabilities.models.errors import ErrorClassification

    assert {c.value for c in ErrorClassification} == {"business_outcome", "recoverable", "hard_failure"}
