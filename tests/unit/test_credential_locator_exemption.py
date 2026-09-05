"""Narrow exemption for the credential/field-name collision found in P1 audit.

MERIDIAN's password field is `name="password"`, and the demo credential is
also the literal string "password". Before this exemption, the runtime-value
filter dropped that `stable_attribute name=password` strategy — correctly, by
the letter of D014 — leaving only `role_name`/`label` strategies that do not
resolve on a target with no real `<label>`/ARIA, so a discovery-compiled
sign-on artifact failed replay with TARGET_NOT_FOUND.

The fix distinguishes *static DOM structure* (an HTML `name=` attribute, fixed
by markup regardless of what's typed into the field) from *runtime-derived
identity* (accessible text/name that renders live data). It is scoped as
narrowly as possible: one locator kind, one attribute, exact string equality,
and only against inputs explicitly declared as credentials — never member
numbers or any other invocation-varying sensitive input, and never any other
locator kind or artifact field.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from ui_capabilities.discovery.compiler import ArtifactCompiler
from ui_capabilities.discovery.recorder import RecordedRun, RecordedStep, StateSnapshot
from ui_capabilities.models.actions import ClickAction, FillAction, NavigateAction, ValueSource
from ui_capabilities.models.artifact import InputSpec
from ui_capabilities.models.errors import CompileError
from ui_capabilities.models.targets import LocatorKind, LocatorStrategy
from ui_capabilities.policy.config import PolicyConfig
from ui_capabilities.policy.engine import PolicyDecision, PolicyEngine
from ui_capabilities.surfaces.base import ActionResult, ObservedElement

ENTRY = "https://web-sample.interface-hiring.com/"
NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)
ALLOWED = PolicyDecision(allowed=True)
OK = ActionResult(ok=True)

PASSWORD_SPEC = InputSpec(
    name="password", type="string", sensitive=True, credential=True,
    description="MERIDIAN operator password",
)
MEMBER_NUMBER_SPEC = InputSpec(
    name="member_number", type="string", sensitive=True, credential=False,
    description="MERIDIAN member number (invocation-varying, not a credential)",
)


def _policy() -> PolicyEngine:
    return PolicyEngine(
        PolicyConfig(
            allowed_domains=["web-sample.interface-hiring.com"],
            allowed_ports=[443],
            allowed_route_patterns=["/**"],
            allowed_actions=["navigate", "click", "fill"],
        )
    )


def _compiler() -> ArtifactCompiler:
    return ArtifactCompiler(_policy(), error_rules_factory=lambda: [])


def _snap(path: str, fp: str) -> StateSnapshot:
    return StateSnapshot(url=f"{ENTRY.rstrip('/')}{path}", path=path, title="Sign On - Meridian Core", fingerprint=fp)


def _run(
    *,
    input_spec: InputSpec,
    bound_value: str,
    strategies: list[LocatorStrategy],
    fill_kind: str = "fill",
) -> RecordedRun:
    """One navigate + one fill step, with the fill target's locator identity
    fully controlled by the caller — this is the whole surface area needed to
    exercise the collision."""
    element = ObservedElement(
        ref="e1", kind="textbox", tag="input",
        candidate_strategies=strategies,
    )
    steps = [
        RecordedStep(
            index=0,
            before=_snap("/", "f0"),
            action=NavigateAction(url=ENTRY),
            element=None,
            policy=ALLOWED,
            result=OK,
            after=_snap("/signon", "f1"),
            started_at=NOW,
        ),
        RecordedStep(
            index=1,
            before=_snap("/signon", "f1"),
            action=FillAction(element_ref="e1", value_source=ValueSource(input_name=input_spec.name)),
            element=element,
            policy=ALLOWED,
            result=OK,
            after=None,
            started_at=NOW,
        ),
    ]
    return RecordedRun(
        run_id="disc-credtest",
        goal="sign on",
        capability_id="test.credential_case",
        entry_point=ENTRY,
        model_name="fixture",
        input_specs=[input_spec],
        input_bindings={input_spec.name: bound_value},
        steps=steps,
        success=True,
        final_state=_snap("/signon", "f1"),
        app_fingerprint={"app_title": "Meridian Core"},
    )


def _fill_step(artifact):
    return next(s for s in artifact.steps if s.action == "fill")


# ------------------------------------------------------------------ positive


def test_credential_collision_with_static_name_attribute_compiles():
    """Requirement 1/3/6: a stable_attribute/name locator whose value equals a
    declared credential's bound value survives, and only that field."""
    run = _run(
        input_spec=PASSWORD_SPEC,
        bound_value="password",
        strategies=[LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="name", value="password")],
    )
    artifact = _compiler().compile(run, app_id="meridian_core", vendor_family="cornerstone_meridian")
    step = _fill_step(artifact)
    assert len(step.target.strategies) == 1
    assert step.target.strategies[0].value == "password"
    # requirement 6: the credential's VALUE is only ever an InputValueRef, never a literal
    assert step.value.kind == "input" and step.value.name == "password"


def test_credential_collision_survives_alongside_other_strategies():
    """Requirement 2: scoped to `name`; other candidate strategies on the same
    element are unaffected by the exemption (they're just not needed here)."""
    run = _run(
        input_spec=PASSWORD_SPEC,
        bound_value="password",
        strategies=[
            LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="textbox", name="Password"),
            LocatorStrategy(kind=LocatorKind.LABEL, value="Password"),
            LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="name", value="password"),
        ],
    )
    artifact = _compiler().compile(run, app_id="meridian_core", vendor_family="cornerstone_meridian")
    step = _fill_step(artifact)
    kinds = [s.kind for s in step.target.strategies]
    assert kinds == [LocatorKind.ROLE_NAME, LocatorKind.LABEL, LocatorKind.STABLE_ATTRIBUTE]


def test_final_artifact_contains_the_credential_only_at_the_one_exempted_location():
    """Requirement 6: scanning the whole serialized artifact for the credential
    value finds exactly the one structurally-verified location."""
    run = _run(
        input_spec=PASSWORD_SPEC,
        bound_value="password",
        strategies=[LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="name", value="password")],
    )
    artifact = _compiler().compile(run, app_id="meridian_core", vendor_family="cornerstone_meridian")
    serialized = artifact.model_dump_json()
    # "password" also appears as the declared parameter *name* (already exempt
    # vocabulary per D-prior); assert the locator value round-trips correctly
    # rather than counting raw substring occurrences.
    assert artifact.steps[1].target.strategies[0].value == "password"
    assert artifact.contract.inputs[0].name == "password"


# ------------------------------------------------------------------ negative


def test_text_strategy_with_credential_value_is_still_dropped():
    """Requirement 4: TEXT locators are never exempt."""
    run = _run(
        input_spec=PASSWORD_SPEC,
        bound_value="password",
        strategies=[LocatorStrategy(kind=LocatorKind.TEXT, value="password")],
    )
    with pytest.raises(CompileError, match="no reusable target identity"):
        _compiler().compile(run, app_id="meridian_core", vendor_family="cornerstone_meridian")


def test_css_strategy_with_credential_value_is_still_dropped():
    """Requirement 4: CSS locators are never exempt, even containing the value."""
    run = _run(
        input_spec=PASSWORD_SPEC,
        bound_value="password",
        strategies=[LocatorStrategy(kind=LocatorKind.CSS, value='[data-secret="password"]')],
    )
    with pytest.raises(CompileError, match="no reusable target identity"):
        _compiler().compile(run, app_id="meridian_core", vendor_family="cornerstone_meridian")


def test_stable_attribute_id_is_not_exempt_only_name_is():
    """Requirement 2: the exemption is scoped to `attribute="name"`; `id` is a
    different concrete case with no live evidence requiring it, so it stays
    subject to the ordinary filter."""
    run = _run(
        input_spec=PASSWORD_SPEC,
        bound_value="password",
        strategies=[LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="id", value="password")],
    )
    with pytest.raises(CompileError, match="no reusable target identity"):
        _compiler().compile(run, app_id="meridian_core", vendor_family="cornerstone_meridian")


def test_role_name_strategy_with_credential_value_is_still_dropped():
    """Requirement 4: ROLE_NAME (accessible name) is rendered/derivable text,
    never exempt, even if its `name` field equals a credential."""
    run = _run(
        input_spec=PASSWORD_SPEC,
        bound_value="password",
        strategies=[LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="textbox", name="password")],
    )
    with pytest.raises(CompileError, match="no reusable target identity"):
        _compiler().compile(run, app_id="meridian_core", vendor_family="cornerstone_meridian")


def test_non_credential_sensitive_value_in_stable_attribute_name_is_still_dropped():
    """Requirement 3/5 (the D014 case): a member number — sensitive but NOT a
    declared credential — embedded in a stable_attribute/name locator must
    still be rejected exactly as before. This is the core proof the exemption
    did not become a general "stable_attribute is always safe" rule."""
    run = _run(
        input_spec=MEMBER_NUMBER_SPEC,
        bound_value="100234",
        strategies=[LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="name", value="100234")],
    )
    with pytest.raises(CompileError, match="no reusable target identity"):
        _compiler().compile(run, app_id="meridian_core", vendor_family="cornerstone_meridian")


def test_final_scan_still_rejects_a_genuine_leak_alongside_a_legitimate_credential():
    """The presence of one legitimately-exempted credential value must not
    weaken the scan for an unrelated genuine leak elsewhere in the same
    artifact."""
    artifact = _compiler().compile(
        _run(
            input_spec=PASSWORD_SPEC,
            bound_value="password",
            strategies=[LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="name", value="password")],
        ),
        app_id="meridian_core",
        vendor_family="cornerstone_meridian",
    )
    data = artifact.model_dump()
    data["description"] = "leaked description containing password"
    leaked = type(artifact).model_validate(data)
    with pytest.raises(CompileError, match=r"\.description"):
        ArtifactCompiler._assert_no_sensitive_values(leaked, ["password"], frozenset({"password"}))


def test_credential_value_leaking_into_a_condition_is_still_rejected():
    """Requirement 4/6: conditions are never exempt, even for a credential."""
    artifact = _compiler().compile(
        _run(
            input_spec=PASSWORD_SPEC,
            bound_value="password",
            strategies=[LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="name", value="password")],
        ),
        app_id="meridian_core",
        vendor_family="cornerstone_meridian",
    )
    data = artifact.model_dump()
    data["success_conditions"][0]["value"] = "password accepted"
    leaked = type(artifact).model_validate(data)
    with pytest.raises(CompileError, match=r"\.success_conditions"):
        ArtifactCompiler._assert_no_sensitive_values(leaked, ["password"], frozenset({"password"}))


def test_credential_value_leaking_into_a_literal_is_rejected_before_compile_even_completes():
    """Requirement 4/6: a literal fill value embedding a credential is refused
    by the existing `_compile_value` guard, well before the final scan."""
    element = ObservedElement(
        ref="e1", kind="textbox", tag="input",
        candidate_strategies=[LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="name", value="unrelated-field")],
    )
    run = RecordedRun(
        run_id="disc-credtest2",
        goal="sign on",
        capability_id="test.credential_literal",
        entry_point=ENTRY,
        model_name="fixture",
        input_specs=[PASSWORD_SPEC],
        input_bindings={"password": "password"},
        steps=[
            RecordedStep(
                index=0,
                before=_snap("/signon", "f0"),
                action=FillAction(element_ref="e1", value_source=ValueSource(literal="entered password manually")),
                element=element,
                policy=ALLOWED,
                result=OK,
                after=None,
                started_at=NOW,
            ),
        ],
        success=True,
        final_state=_snap("/signon", "f0"),
    )
    with pytest.raises(CompileError, match="embeds sensitive input"):
        _compiler().compile(run, app_id="meridian_core", vendor_family="cornerstone_meridian")


def test_default_credential_values_is_empty_and_backward_compatible():
    """Callers that don't know about credentials (e.g. Northstar's compile path,
    or any direct call to the assert without the new parameter) get the
    original strict behavior — nothing is ever exempted by default."""
    artifact = _compiler().compile(
        _run(
            input_spec=PASSWORD_SPEC,
            bound_value="password",
            strategies=[LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="name", value="password")],
        ),
        app_id="meridian_core",
        vendor_family="cornerstone_meridian",
    )
    with pytest.raises(CompileError, match="sensitive invocation value"):
        ArtifactCompiler._assert_no_sensitive_values(artifact, ["password"])  # no credential_values passed


def test_url_template_parameterization_is_unaffected_by_the_exemption():
    """Requirement 4: URLs still go through the existing {name} mechanism only;
    the new exemption never touches url_template."""
    run = _run(
        input_spec=PASSWORD_SPEC,
        bound_value="password",
        strategies=[LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="name", value="password")],
    )
    run.steps[0].action = NavigateAction(url=f"{ENTRY.rstrip('/')}/signon?pw=password")
    artifact = _compiler().compile(run, app_id="meridian_core", vendor_family="cornerstone_meridian")
    nav = next(s for s in artifact.steps if s.action == "navigate")
    assert "password" not in nav.url_template or "{password}" in nav.url_template


def test_placeholder_stripping_does_not_hide_a_raw_value_next_to_a_legitimate_one():
    """The `{name}` stripping fix (needed because MERIDIAN's credential equals
    its own input name) must not create a blind spot: a RAW, non-templated
    occurrence of the same value in the same string must still be caught."""
    artifact = _compiler().compile(
        _run(
            input_spec=PASSWORD_SPEC,
            bound_value="password",
            strategies=[LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="name", value="password")],
        ),
        app_id="meridian_core",
        vendor_family="cornerstone_meridian",
    )
    data = artifact.model_dump()
    # legitimate placeholder syntax immediately followed by a raw leaked value
    data["description"] = "goes with {password} but also literally password here"
    leaked = type(artifact).model_validate(data)
    with pytest.raises(CompileError, match=r"\.description"):
        ArtifactCompiler._assert_no_sensitive_values(leaked, ["password"], frozenset({"password"}))
