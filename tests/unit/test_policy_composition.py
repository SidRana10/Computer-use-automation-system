"""Regression: a capability artifact may narrow global route privileges but
must never broaden them.

The original `_pattern_within` accepted any candidate whose literal string
prefix started with a global pattern's literal prefix. Because the global
policy allows `/`, that let an artifact introduce ANY absolute route the
global policy had never permitted.
"""

import pytest

from ui_capabilities.models.artifact import CapabilityPolicy
from ui_capabilities.models.errors import RiskLevel
from ui_capabilities.policy.config import default_demo_policy
from ui_capabilities.policy.engine import PolicyEngine

GLOBAL_ENTRY = "http://127.0.0.1:8001"


def _capability(routes: list[str]) -> CapabilityPolicy:
    return CapabilityPolicy(
        allowed_domains=["127.0.0.1"],
        allowed_route_patterns=routes,
        allowed_actions=["navigate", "click", "fill", "select", "extract", "wait_for", "assert"],
        max_unattended_risk=RiskLevel.REVERSIBLE,
        require_human_for=[RiskLevel.RISKY, RiskLevel.IRREVERSIBLE],
    )


def test_artifact_cannot_introduce_route_global_policy_forbids():
    """The exact demonstrated bypass: global forbids /admin, artifact asks for
    /admin/**, narrowed policy must still forbid /admin."""
    base = default_demo_policy(GLOBAL_ENTRY)
    assert not PolicyEngine(base).check_url(f"{GLOBAL_ENTRY}/admin/secret").allowed

    narrowed = base.narrowed_by(_capability(["/admin/**"]))

    assert "/admin/**" not in narrowed.allowed_route_patterns
    decision = PolicyEngine(narrowed).check_url(f"{GLOBAL_ENTRY}/admin/secret")
    assert not decision.allowed
    assert decision.code == "ROUTE_BLOCKED"


@pytest.mark.parametrize(
    "hostile_route",
    ["/admin/**", "/internal/*", "/", "/**", "/members/../admin", "/demo/config"],
)
def test_no_hostile_route_escapes_global_policy(hostile_route):
    """Generic property: for every candidate route an artifact declares, no
    path it admits may fall outside the global policy."""
    base = default_demo_policy(GLOBAL_ENTRY)
    narrowed = base.narrowed_by(_capability([hostile_route]))
    engine = PolicyEngine(narrowed)
    for probe in ("/admin/secret", "/demo/config", "/internal/keys", "/etc/passwd"):
        assert not engine.check_url(f"{GLOBAL_ENTRY}{probe}").allowed, f"{hostile_route} admitted {probe}"


def test_legitimate_narrowing_still_accepted():
    """The routes the real canonical capability declares must survive."""
    base = default_demo_policy(GLOBAL_ENTRY)
    real_routes = ["/", "/members/*", "/members/*/accounts", "/members/search", "/session/**"]
    narrowed = base.narrowed_by(_capability(real_routes))

    assert set(narrowed.allowed_route_patterns) == set(real_routes)
    engine = PolicyEngine(narrowed)
    for allowed in ("/", "/members/search", "/members/M-10003", "/members/M-10003/accounts", "/session/continue"):
        assert engine.check_url(f"{GLOBAL_ENTRY}{allowed}").allowed, allowed


def test_narrowing_actually_narrows():
    """A capability that only needs /members/** must not retain /session/**."""
    base = default_demo_policy(GLOBAL_ENTRY)
    narrowed = base.narrowed_by(_capability(["/members/**"]))
    engine = PolicyEngine(narrowed)
    assert engine.check_url(f"{GLOBAL_ENTRY}/members/M-10001").allowed
    assert not engine.check_url(f"{GLOBAL_ENTRY}/session/continue").allowed
