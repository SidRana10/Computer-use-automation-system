"""Regression: recovery actions cross the same policy boundary as ordinary
steps. Previously `perform_recovery` called `surface.execute()` directly, so a
declared recovery could reach the surface without authorization.
"""

import pytest

from tests.fixtures.fakes import FakeSurface
from ui_capabilities.models.artifact import ErrorRule, RecoveryActionSpec
from ui_capabilities.models.conditions import ConditionKind, ConditionSpec
from ui_capabilities.models.errors import ErrorClassification, RiskLevel
from ui_capabilities.models.targets import LocatorKind, LocatorStrategy, TargetDescriptor
from ui_capabilities.policy.config import default_demo_policy
from ui_capabilities.policy.engine import PolicyEngine
from ui_capabilities.replay.recovery import perform_recovery

ENTRY = "http://127.0.0.1:8001"


def _rule(recovery: list[RecoveryActionSpec]) -> ErrorRule:
    return ErrorRule(
        code="KNOWN_INTERSTITIAL",
        classification=ErrorClassification.RECOVERABLE,
        when=[ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="idle")],
        recovery=recovery,
        max_attempts=2,
        caller_message="dismissed",
    )


def _target(name: str) -> TargetDescriptor:
    return TargetDescriptor(
        description=name,
        strategies=[LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="button", name=name)],
    )


async def test_allowed_recovery_action_executes(tmp_path):
    surface = FakeSurface(tmp_path)
    policy = PolicyEngine(default_demo_policy(ENTRY))
    rule = _rule([RecoveryActionSpec(kind="dismiss", target=_target("Continue"))])

    outcome = await perform_recovery(surface, rule, policy)

    assert not outcome.denied
    assert len(surface.executed) == 1
    assert surface.executed[0].kind == "click"
    assert outcome.notes == ["dismiss -> ok"]


async def test_wait_recovery_needs_no_surface_execution(tmp_path):
    surface = FakeSurface(tmp_path)
    policy = PolicyEngine(default_demo_policy(ENTRY))
    outcome = await perform_recovery(surface, _rule([RecoveryActionSpec(kind="wait", wait_ms=1)]), policy)
    assert not outcome.denied
    assert surface.executed == []


async def test_policy_denied_recovery_never_reaches_the_surface(tmp_path):
    """A recovery that would click an irreversible control is denied by the
    same risk classifier that guards ordinary steps."""
    surface = FakeSurface(tmp_path)
    policy = PolicyEngine(default_demo_policy(ENTRY))
    rule = _rule([RecoveryActionSpec(kind="dismiss", target=_target("Confirm Open Account"))])

    outcome = await perform_recovery(surface, rule, policy)

    assert outcome.denied
    assert outcome.denied_action == "dismiss"
    assert outcome.denial.requires_human
    assert surface.executed == [], "denied recovery must never call SurfaceAdapter.execute"


async def test_recovery_denied_when_action_kind_not_permitted(tmp_path):
    """Effective policy without 'navigate' must block a reload recovery."""
    config = default_demo_policy(ENTRY)
    config.allowed_actions = [a for a in config.allowed_actions if a != "navigate"]
    surface = FakeSurface(tmp_path)

    outcome = await perform_recovery(surface, _rule([RecoveryActionSpec(kind="reload")]), PolicyEngine(config))

    assert outcome.denied
    assert outcome.denied_action == "reload"
    assert outcome.denial.code == "ACTION_BLOCKED"
    assert surface.executed == []


async def test_recovery_stops_at_first_denial(tmp_path):
    """Later recovery actions must not run once one is denied."""
    surface = FakeSurface(tmp_path)
    policy = PolicyEngine(default_demo_policy(ENTRY))
    rule = _rule(
        [
            RecoveryActionSpec(kind="dismiss", target=_target("Confirm Open Account")),
            RecoveryActionSpec(kind="dismiss", target=_target("Continue")),
        ]
    )

    outcome = await perform_recovery(surface, rule, policy)

    assert outcome.denied
    assert surface.executed == []
