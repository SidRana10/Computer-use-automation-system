"""Deterministic scripted model adapters — TEST DOUBLES ONLY.

They exercise the same orchestration/compiler wiring as the real model without
paid API calls. They can never be used to produce the genuine discovery
evidence (`evidence/discovery_run.jsonl`).
"""

from __future__ import annotations

from ..models.actions import (
    ClickAction,
    DiscoveryAction,
    DoneAction,
    ExtractAction,
    FillAction,
    NavigateAction,
    RequestHumanAction,
    SelectAction,
    SuggestedCondition,
    ValueSource,
)
from ..surfaces.base import Observation, ObservedElement
from .model_adapter import TurnContext


def _find(observation: Observation, *, kind: str | None = None, name_contains: str | None = None, id_attr: str | None = None) -> ObservedElement | None:
    for el in observation.elements:
        if kind and el.kind != kind:
            continue
        if id_attr and el.id_attr != id_attr:
            continue
        if name_contains:
            haystack = " ".join(filter(None, [el.accessible_name, el.label, el.placeholder, el.text])).lower()
            if name_contains.lower() not in haystack:
                continue
        return el
    return None


class ScriptedBalanceModel:
    """Scripted flow for the savings-balance goal against the demo app."""

    name = "fake"

    def __init__(self) -> None:
        self._filled = False
        self._extracted = False

    async def next_action(self, observation: Observation, context: TurnContext) -> DiscoveryAction:
        path = observation.path
        if path == "/":
            link = _find(observation, kind="link", name_contains="Member Search")
            if link:
                return ClickAction(element_ref=link.ref, rationale_summary="Open member search")
        if path == "/members/search":
            field = _find(observation, kind="textbox", name_contains="Member ID")
            if field and not self._filled:
                self._filled = True
                return FillAction(
                    element_ref=field.ref,
                    value_source=ValueSource(input_name="member_id"),
                    rationale_summary="Enter the requested member identifier",
                )
            button = _find(observation, kind="button", name_contains="Search")
            if button:
                return ClickAction(element_ref=button.ref, rationale_summary="Submit search")
        if path.startswith("/members/") and path.endswith("/accounts"):
            cell = _find(observation, kind="cell", id_attr="acct-sav-balance")
            if cell and not self._extracted:
                self._extracted = True
                return ExtractAction(
                    element_ref=cell.ref,
                    output_name="savings_balance",
                    output_type="decimal",
                    rationale_summary="Read current savings balance",
                )
            return DoneAction(
                success_summary="Savings balance extracted from accounts table",
                suggested_success_condition=SuggestedCondition(kind="text_present", value="Savings"),
            )
        if path.startswith("/members/"):
            link = _find(observation, kind="link", name_contains="Accounts")
            if link:
                return ClickAction(element_ref=link.ref, rationale_summary="Open accounts view")
        return RequestHumanAction(reason_code="blocked", message="Scripted flow has no next action for this page")


class ScriptedSubAccountModel:
    """Scripted flow for the risky sub-account goal; ends at the irreversible
    confirm, which policy must route to a human."""

    name = "fake-subaccount"

    def __init__(self) -> None:
        self._filled = False

    async def next_action(self, observation: Observation, context: TurnContext) -> DiscoveryAction:
        path = observation.path
        if path == "/":
            link = _find(observation, kind="link", name_contains="Member Search")
            if link:
                return ClickAction(element_ref=link.ref, rationale_summary="Open member search")
        if path == "/members/search":
            field = _find(observation, kind="textbox", name_contains="Member ID")
            if field and not self._filled:
                self._filled = True
                return FillAction(
                    element_ref=field.ref,
                    value_source=ValueSource(input_name="member_id"),
                    rationale_summary="Enter the requested member identifier",
                )
            button = _find(observation, kind="button", name_contains="Search")
            if button:
                return ClickAction(element_ref=button.ref, rationale_summary="Submit search")
        if path.endswith("/subaccounts/new"):
            select = _find(observation, kind="combobox", name_contains="Account Type")
            if select:
                return SelectAction(
                    element_ref=select.ref,
                    value_source=ValueSource(input_name="account_type"),
                    rationale_summary="Choose requested sub-account type",
                )
        if "Review New Sub-Account" in observation.visible_text_summary:
            confirm = _find(observation, kind="button", name_contains="Confirm Open Account")
            if confirm:
                return ClickAction(element_ref=confirm.ref, rationale_summary="Finalize sub-account opening")
        if path.endswith("/subaccounts/confirmed") or "Sub-Account Opened" in observation.visible_text_summary:
            return DoneAction(
                success_summary="Sub-account opened and confirmation visible",
                suggested_success_condition=SuggestedCondition(kind="text_present", value="Sub-account opened successfully."),
            )
        if path.endswith("/subaccounts/new") or "Open Sub-Account" not in observation.visible_text_summary:
            review = _find(observation, kind="button", name_contains="Review")
            if review:
                return ClickAction(element_ref=review.ref, rationale_summary="Proceed to review")
        if path.startswith("/members/"):
            link = _find(observation, kind="link", name_contains="Open Sub-Account")
            if link:
                return ClickAction(element_ref=link.ref, rationale_summary="Open sub-account form")
        return RequestHumanAction(reason_code="blocked", message="Scripted flow has no next action for this page")


class RogueModel:
    """Adversarial test double: immediately proposes an off-policy navigation.
    Exists to prove the policy gate blocks before the surface executes."""

    name = "rogue"

    def __init__(self) -> None:
        self._tried = False

    async def next_action(self, observation: Observation, context: TurnContext) -> DiscoveryAction:
        if not self._tried:
            self._tried = True
            return NavigateAction(url="https://evil.example.com/exfiltrate", rationale_summary="")
        return RequestHumanAction(reason_code="blocked", message="Rogue action was blocked")
