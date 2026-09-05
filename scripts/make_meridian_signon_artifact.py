#!/usr/bin/env python3
"""Author the MERIDIAN sign-on capability artifact.

Hand-authored rather than discovery-recorded, following the Phase-1 precedent in
`make_subaccount_artifact.py`. Sign-on is the prerequisite for every other
MERIDIAN capability, so it has to exist before a discovery run can reach any
screen behind it. Later MERIDIAN capabilities are recorded through the normal
discovery path.

Locator note: MERIDIAN renders no `id`, `aria-label` or `<label>` elements, so
the form `name` attribute is the primary durable identity and the accessible
role/name of the submit button (its `value` caption) is the secondary. This is
the ordinary strategy chain, not a positional fallback.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ui_capabilities.discovery.compiler import save_artifact  # noqa: E402
from ui_capabilities.models.artifact import (  # noqa: E402
    ApprovalState,
    CapabilityArtifact,
    CapabilityContract,
    CapabilityPolicy,
    InputValueRef,
    Provenance,
    StepSpec,
    TargetAppSpec,
)
from ui_capabilities.models.conditions import ConditionKind, ConditionSpec  # noqa: E402
from ui_capabilities.models.errors import RiskLevel  # noqa: E402
from ui_capabilities.models.targets import LocatorKind, LocatorStrategy, TargetDescriptor  # noqa: E402
from ui_capabilities.targets import get_profile  # noqa: E402


def _field(name: str, caption: str, kind: str = "textbox") -> TargetDescriptor:
    return TargetDescriptor(
        description=f"{kind} '{caption}'",
        strategies=[
            LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="name", value=name),
            LocatorStrategy(kind=LocatorKind.ROLE_NAME, role=kind, name=caption),
        ],
    )


def build(entry_point: str) -> CapabilityArtifact:
    profile = get_profile("meridian")
    on_menu = [
        ConditionSpec(kind=ConditionKind.URL_MATCHES, value="/menu"),
        ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="MAIN MENU"),
    ]
    return CapabilityArtifact(
        capability_id="meridian.sign_on",
        capability_version="1.0.0",
        name="MERIDIAN operator sign-on",
        description="Sign on to MERIDIAN CORE as the supplied operator and reach the main menu.",
        approval_state=ApprovalState.DRAFT,
        risk_level=RiskLevel.REVERSIBLE,
        target=TargetAppSpec(
            app_id=profile.app_id,
            vendor_family=profile.vendor_family,
            surface_kind="web",
            entry_point=entry_point,
            app_fingerprint={"app_title": profile.title_marker, "build_marker": "4.2.1"},
        ),
        contract=CapabilityContract(
            inputs=[
                profile.input_specs["operator_id"],
                profile.input_specs["password"],
                profile.input_specs["branch"],
            ],
            outputs=[],
        ),
        steps=[
            StepSpec(
                id="s1_navigate",
                name="Open the MERIDIAN sign-on screen",
                action="navigate",
                url_template="/signon",
                checkpoint_after=[
                    ConditionSpec(kind=ConditionKind.URL_MATCHES, value="/signon"),
                    ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="OPERATOR SIGN ON"),
                ],
            ),
            StepSpec(
                id="s2_fill",
                name="Fill Operator ID",
                action="fill",
                target=_field("operator", "Operator ID"),
                value=InputValueRef(name="operator_id"),
                risk=RiskLevel.REVERSIBLE,
            ),
            StepSpec(
                id="s3_fill",
                name="Fill Password",
                action="fill",
                target=_field("password", "Password"),
                value=InputValueRef(name="password"),
                risk=RiskLevel.REVERSIBLE,
            ),
            StepSpec(
                id="s4_select",
                name="Select Branch",
                action="select",
                target=_field("branch", "Branch", kind="combobox"),
                value=InputValueRef(name="branch"),
                risk=RiskLevel.REVERSIBLE,
            ),
            StepSpec(
                id="s5_click",
                name="Click Sign On",
                action="click",
                target=TargetDescriptor(
                    description="button 'Sign On'",
                    strategies=[
                        LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="button", name="Sign On"),
                        LocatorStrategy(kind=LocatorKind.CSS, value='input[type="submit"][value="Sign On"]'),
                    ],
                ),
                risk=RiskLevel.SAFE,
                checkpoint_after=on_menu,
            ),
        ],
        success_conditions=on_menu,
        error_rules=profile.error_rules_factory(),
        policy=CapabilityPolicy(
            allowed_domains=[profile.policy(entry_point).allowed_domains[0]],
            allowed_route_patterns=["/signon", "/menu"],
            allowed_actions=["navigate", "click", "fill", "select", "wait_for", "assert"],
            max_unattended_risk=RiskLevel.REVERSIBLE,
            require_human_for=[RiskLevel.RISKY, RiskLevel.IRREVERSIBLE],
            # Sign-on has no supervisor-gated step, so nothing routes to a human.
            escalate_on_codes=[],
        ),
        provenance=Provenance(
            discovery_run_id="hand-authored-meridian-signon",
            discovered_at=datetime(2026, 9, 5, tzinfo=timezone.utc),
            discovery_model="hand-authored (prerequisite for reaching any authenticated MERIDIAN screen)",
            source_app_fingerprint={"app_title": profile.title_marker},
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=get_profile("meridian").default_entry_point)
    parser.add_argument("--output", default="artifacts/meridian/meridian.sign_on.v1.json")
    args = parser.parse_args()
    artifact = build(args.target)
    save_artifact(artifact, args.output)
    print(f"artifact: {args.output}")


if __name__ == "__main__":
    main()
