"""Locator resolution behavior against the live app, and bounded-retry
exhaustion turning into a hard failure."""

import pytest

from tests.fixtures.factories import make_balance_artifact
from ui_capabilities.models.targets import LocatorKind, LocatorStrategy, TargetDescriptor
from ui_capabilities.surfaces.locator_resolver import resolve_target

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("demo_state", "cleanup_surface")]


async def test_resolver_walks_ordered_chain_and_reports_match(demo_server, harness):
    await harness.surface.start(f"{demo_server}/members/search")
    target = TargetDescriptor(
        description="search button",
        strategies=[
            LocatorStrategy(kind=LocatorKind.LABEL, value="Nonexistent Label"),  # first strategy misses
            LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="button", name="Search"),
        ],
    )
    outcome = await resolve_target(harness.surface.page, target, timeout_ms=2000)
    assert outcome.status == "resolved"
    assert outcome.matched_strategy.kind == LocatorKind.ROLE_NAME  # fallback position logged for drift telemetry


async def test_resolver_rejects_ambiguous_matches(demo_server, harness):
    await harness.surface.start(f"{demo_server}/members/search")
    target = TargetDescriptor(
        description="ambiguous text",
        strategies=[LocatorStrategy(kind=LocatorKind.TEXT, value="Member", exact=False)],
    )
    outcome = await resolve_target(harness.surface.page, target, timeout_ms=800)
    assert outcome.status == "ambiguous"
    assert "matched" in outcome.detail


async def test_resolver_not_found_after_bounded_wait(demo_server, harness):
    await harness.surface.start(f"{demo_server}/members/search")
    target = TargetDescriptor(
        description="ghost control",
        strategies=[LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="button", name="Ghost Button")],
    )
    outcome = await resolve_target(harness.surface.page, target, timeout_ms=600)
    assert outcome.status == "not_found"
    assert "no strategy" in outcome.detail


async def test_exhausted_recovery_becomes_hard_failure(demo_server, demo_state, replay_engine):
    """Cripple the TRANSIENT_LOAD recovery (wait only, no reload) so the
    static loading page never clears: bounded attempts must exhaust into
    RETRY_EXHAUSTED, not loop forever."""
    demo_state.slow_accounts_pending = True
    artifact = make_balance_artifact(demo_server)
    for rule in artifact.error_rules:
        if rule.code == "TRANSIENT_LOAD":
            rule.recovery = [r for r in rule.recovery if r.kind == "wait"]
            for r in rule.recovery:
                r.wait_ms = 200
    result = await replay_engine().replay(artifact, {"member_id": "M-10001"})
    assert result.status == "failure"
    assert result.code == "RETRY_EXHAUSTED"
    assert result.step_id == "s4_click"
    assert result.recovery_attempts >= 2
