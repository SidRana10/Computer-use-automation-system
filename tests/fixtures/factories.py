"""Hand-authored fixture artifacts (schema-valid, equivalent to compiled
output) and small fakes for unit tests."""

from __future__ import annotations

from datetime import datetime, timezone

from ui_capabilities.discovery.profiles import demo_app_error_rules
from ui_capabilities.models.artifact import (
    CapabilityArtifact,
    CapabilityContract,
    CapabilityPolicy,
    InputSpec,
    InputValueRef,
    OutputSpec,
    Provenance,
    StepSpec,
    TargetAppSpec,
)
from ui_capabilities.models.conditions import ConditionKind, ConditionSpec
from ui_capabilities.models.errors import RiskLevel
from ui_capabilities.models.targets import LocatorKind, LocatorStrategy, TargetDescriptor

APP_TITLE = "Northstar Credit Union — Member Servicing Console (Demo)"


def _target(entry_point: str) -> TargetAppSpec:
    return TargetAppSpec(
        app_id="northstar_member_servicing_demo",
        vendor_family="northstar_servicing",
        surface_kind="web",
        entry_point=entry_point,
        app_fingerprint={"app_title": "Northstar Credit Union", "build_marker": "4.2.19-legacy"},
    )


def _policy(host: str) -> CapabilityPolicy:
    return CapabilityPolicy(
        allowed_domains=[host],
        allowed_route_patterns=["/", "/members/**", "/session/**"],
        allowed_actions=["navigate", "click", "fill", "select", "extract", "wait_for", "assert"],
        max_unattended_risk=RiskLevel.REVERSIBLE,
        require_human_for=[RiskLevel.RISKY, RiskLevel.IRREVERSIBLE],
    )


def _provenance() -> Provenance:
    return Provenance(
        discovery_run_id="fixture-authored",
        discovered_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        discovery_model="fixture (hand-authored equivalent of compiled output)",
        source_app_fingerprint={"app_title": "Northstar Credit Union"},
    )


def make_balance_artifact(entry_point: str, *, member_id_pattern: str | None = r"M-\d{5}") -> CapabilityArtifact:
    host = entry_point.split("//")[1].split(":")[0].split("/")[0]
    return CapabilityArtifact(
        capability_id="member.get_savings_balance",
        capability_version="1.0.0",
        name="Get member savings balance",
        description="Searches a member by identifier and returns the current savings balance.",
        risk_level=RiskLevel.SAFE,
        target=_target(entry_point),
        contract=CapabilityContract(
            inputs=[
                InputSpec(
                    name="member_id",
                    type="string",
                    sensitive=True,
                    pattern=member_id_pattern,
                    description="Member identifier in the demo format M-#####",
                )
            ],
            outputs=[
                OutputSpec(
                    name="savings_balance",
                    type="decimal",
                    description="Current savings balance in USD",
                    sensitive=True,
                    source_step_id="s5_extract",
                )
            ],
        ),
        steps=[
            StepSpec(
                id="s1_navigate",
                name="Navigate to member search",
                action="navigate",
                url_template="/members/search",
                checkpoint_after=[
                    ConditionSpec(kind=ConditionKind.URL_MATCHES, value="/members/search"),
                    ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="Member Search"),
                ],
            ),
            StepSpec(
                id="s2_fill",
                name="Fill member identifier",
                action="fill",
                target=TargetDescriptor(
                    description="textbox 'Member ID'",
                    strategies=[
                        LocatorStrategy(kind=LocatorKind.LABEL, value="Member ID"),
                        LocatorStrategy(kind=LocatorKind.PLACEHOLDER, value="Enter member number (e.g. M-12345)"),
                        LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="name", value="member_id"),
                    ],
                ),
                value=InputValueRef(name="member_id"),
                risk=RiskLevel.REVERSIBLE,
            ),
            StepSpec(
                id="s3_click",
                name="Submit search",
                action="click",
                target=TargetDescriptor(
                    description="button 'Search'",
                    strategies=[
                        LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="button", name="Search"),
                        LocatorStrategy(kind=LocatorKind.TEXT, value="Search"),
                    ],
                ),
                checkpoint_after=[
                    ConditionSpec(kind=ConditionKind.URL_MATCHES, value="/members/*"),
                    ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="Member Summary"),
                ],
            ),
            StepSpec(
                id="s4_click",
                name="Open accounts view",
                action="click",
                target=TargetDescriptor(
                    description="link 'Accounts'",
                    strategies=[
                        LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="link", name="Accounts"),
                        LocatorStrategy(kind=LocatorKind.TEXT, value="Accounts"),
                    ],
                ),
                checkpoint_after=[
                    ConditionSpec(kind=ConditionKind.URL_MATCHES, value="/members/*/accounts"),
                    ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="Current Balance"),
                ],
            ),
            StepSpec(
                id="s5_extract",
                name="Extract savings balance",
                action="extract",
                target=TargetDescriptor(
                    description="cell 'savings current balance'",
                    strategies=[
                        LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="id", value="acct-sav-balance"),
                    ],
                ),
                output_name="savings_balance",
                output_type="decimal",
            ),
        ],
        success_conditions=[
            ConditionSpec(kind=ConditionKind.URL_MATCHES, value="/members/*/accounts"),
            ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="Savings"),
        ],
        error_rules=demo_app_error_rules(),
        policy=_policy(host),
        provenance=_provenance(),
    )


def make_subaccount_artifact(entry_point: str) -> CapabilityArtifact:
    host = entry_point.split("//")[1].split(":")[0].split("/")[0]
    return CapabilityArtifact(
        capability_id="member.open_sub_account",
        capability_version="1.0.0",
        name="Open member sub-account",
        description="Opens a sub-account of the requested type; the final confirmation is irreversible and requires a human operator.",
        risk_level=RiskLevel.IRREVERSIBLE,
        target=_target(entry_point),
        contract=CapabilityContract(
            inputs=[
                InputSpec(
                    name="member_id",
                    type="string",
                    sensitive=True,
                    pattern=r"M-\d{5}",
                    description="Member identifier in the demo format M-#####",
                ),
                InputSpec(
                    name="account_type",
                    type="string",
                    description="Sub-account product type as shown in the console",
                ),
            ],
            outputs=[
                OutputSpec(
                    name="confirmation_number",
                    type="string",
                    description="Confirmation reference of the opened sub-account",
                    sensitive=True,
                    source_step_id="s8_extract",
                )
            ],
        ),
        steps=[
            StepSpec(
                id="s1_navigate",
                name="Navigate to member search",
                action="navigate",
                url_template="/members/search",
                checkpoint_after=[ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="Member Search")],
            ),
            StepSpec(
                id="s2_fill",
                name="Fill member identifier",
                action="fill",
                target=TargetDescriptor(
                    description="textbox 'Member ID'",
                    strategies=[LocatorStrategy(kind=LocatorKind.LABEL, value="Member ID")],
                ),
                value=InputValueRef(name="member_id"),
                risk=RiskLevel.REVERSIBLE,
            ),
            StepSpec(
                id="s3_click",
                name="Submit search",
                action="click",
                target=TargetDescriptor(
                    description="button 'Search'",
                    strategies=[LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="button", name="Search")],
                ),
                checkpoint_after=[ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="Member Summary")],
            ),
            StepSpec(
                id="s4_click",
                name="Open sub-account form",
                action="click",
                target=TargetDescriptor(
                    description="link 'Open Sub-Account'",
                    strategies=[
                        LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="link", name="Open Sub-Account"),
                        LocatorStrategy(kind=LocatorKind.TEXT, value="Open Sub-Account"),
                    ],
                ),
                checkpoint_after=[
                    ConditionSpec(kind=ConditionKind.URL_MATCHES, value="/members/*/subaccounts/new"),
                    ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="Open Sub-Account"),
                ],
            ),
            StepSpec(
                id="s5_select",
                name="Choose account type",
                action="select",
                target=TargetDescriptor(
                    description="combobox 'Account Type'",
                    strategies=[LocatorStrategy(kind=LocatorKind.LABEL, value="Account Type")],
                ),
                value=InputValueRef(name="account_type"),
                risk=RiskLevel.REVERSIBLE,
            ),
            StepSpec(
                id="s6_click",
                name="Proceed to review",
                action="click",
                target=TargetDescriptor(
                    description="button 'Review'",
                    strategies=[LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="button", name="Review")],
                ),
                checkpoint_after=[ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="Review New Sub-Account")],
            ),
            StepSpec(
                id="s7_click",
                name="Confirm open account (irreversible)",
                action="click",
                target=TargetDescriptor(
                    description="button 'Confirm Open Account'",
                    strategies=[LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="button", name="Confirm Open Account")],
                ),
                risk=RiskLevel.IRREVERSIBLE,
                checkpoint_after=[
                    ConditionSpec(kind=ConditionKind.URL_MATCHES, value="/members/*/subaccounts/confirmed"),
                    ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="Sub-account opened successfully."),
                ],
            ),
            StepSpec(
                id="s8_extract",
                name="Extract confirmation number",
                action="extract",
                target=TargetDescriptor(
                    description="cell 'Confirmation #'",
                    strategies=[LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="id", value="confirmation-number")],
                ),
                output_name="confirmation_number",
                output_type="string",
            ),
        ],
        success_conditions=[ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value="Sub-account opened successfully.")],
        error_rules=demo_app_error_rules(),
        policy=_policy(host),
        provenance=_provenance(),
    )
