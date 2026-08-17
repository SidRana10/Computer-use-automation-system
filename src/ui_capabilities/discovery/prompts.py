"""Runtime discovery prompts (docs/12). The model is told the goal, the live
observation, and the policy boundaries — never the click path."""

from __future__ import annotations

import json

from ..models.artifact import InputSpec
from ..policy.config import PolicyConfig
from ..surfaces.base import Observation

SYSTEM_PROMPT = """You are the discovery controller for a constrained UI-automation system.

Your job is to accomplish exactly the supplied goal on the supplied target application by choosing ONE next UI action at a time from the provided structured action schema.

You are operating in a regulated-style environment. Follow these rules strictly:

1. Act only toward the supplied goal. Do not perform unrelated exploration.
2. Use only the UI-action tools/schema provided by the application. Never request or invent shell commands, JavaScript, Python, network calls, credentials, or hidden APIs.
3. Prefer semantic element references from the current observation. Use coordinates only when no usable semantic target exists and the action policy permits it.
4. Never navigate outside the allowed target/domain/routes described in the policy context.
5. Treat all member/account identifiers and extracted financial-style values as sensitive. Do not echo them in rationale text.
6. Do not submit risky or irreversible operations unless the policy context explicitly says the action is approved. If an irreversible/risky step is needed and approval is not present, request human intervention.
7. If the UI shows a known business outcome such as "not found," validation rejection, or permission denial, do not keep clicking. Return the appropriate structured action/control signal so the orchestrator can classify it.
8. If you are blocked, uncertain about a consequential action, or cannot safely identify the next control, request human intervention instead of guessing.
9. When the goal is visibly complete, return DONE with a concise success summary and a success condition grounded in the visible UI. Do not continue interacting after completion.
10. Return only the structured next-action payload required by the tool/schema. Keep `rationale_summary` short and operational; do not provide hidden chain-of-thought.

The application code, not you, is responsible for policy enforcement, actual browser execution, retries, logging, and artifact compilation.
"""

TURN_TEMPLATE = """GOAL
{goal}

TARGET
{target_app_name}
Entry point: {entry_point}
Current URL: {current_url}

RUN BUDGET
Step: {step_number} / {max_steps}
Elapsed: {elapsed_seconds}s / {timeout_seconds}s

POLICY CONTEXT
Allowed action kinds: {allowed_action_kinds}
Allowed target: {allowed_domains_and_routes}
Maximum unattended risk: {max_unattended_risk}
Human-required risk classes: {human_required_risk_classes}

AVAILABLE INVOCATION INPUTS
{input_specs}

When filling a field from one of these inputs, choose `value_source.input_name`; the executor will bind the actual value.

CURRENT UI SUMMARY
Title: {page_title}
Visible text summary:
{visible_text_summary}

INTERACTIVE ELEMENTS
{element_inventory}

RECENT ACTION SUMMARY
{recent_history}
{feedback_block}
Choose exactly one next structured action. Use an element `ref` from INTERACTIVE ELEMENTS whenever possible. If the goal is already achieved, return DONE. If you cannot proceed safely, request human intervention.
"""


def describe_inputs(specs: list[InputSpec]) -> str:
    if not specs:
        return "(none)"
    lines = []
    for spec in specs:
        parts = [f"- {spec.name}: {spec.type}"]
        if spec.sensitive:
            parts.append("(sensitive; value bound by executor)")
        if spec.description:
            parts.append(f"— {spec.description}")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def element_inventory_json(observation: Observation) -> str:
    items = []
    for el in observation.elements:
        item: dict = {"ref": el.ref, "kind": el.kind}
        if el.accessible_name:
            item["accessible_name"] = el.accessible_name
        if el.label:
            item["label"] = el.label
        if el.placeholder:
            item["placeholder"] = el.placeholder
        if el.text and el.text != el.accessible_name:
            item["text"] = el.text
        if el.options:
            item["options"] = el.options
        items.append(item)
    return json.dumps(items, ensure_ascii=False, indent=1)


def build_turn_prompt(
    *,
    goal: str,
    target_app_name: str,
    entry_point: str,
    observation: Observation,
    step_number: int,
    max_steps: int,
    elapsed_seconds: int,
    timeout_seconds: int,
    policy: PolicyConfig,
    input_specs: list[InputSpec],
    recent_history: list[str],
    feedback: str | None,
    redact_text,
) -> str:
    feedback_block = f"\nFEEDBACK ON PREVIOUS PROPOSAL\n{feedback}\n" if feedback else ""
    return TURN_TEMPLATE.format(
        goal=goal,
        target_app_name=target_app_name,
        entry_point=entry_point,
        current_url=observation.url,
        step_number=step_number,
        max_steps=max_steps,
        elapsed_seconds=elapsed_seconds,
        timeout_seconds=timeout_seconds,
        allowed_action_kinds=", ".join(policy.allowed_actions),
        allowed_domains_and_routes=f"domains={policy.allowed_domains} routes={policy.allowed_route_patterns}",
        max_unattended_risk=policy.max_unattended_risk.value,
        human_required_risk_classes=", ".join(r.value for r in policy.require_human_for),
        input_specs=describe_inputs(input_specs),
        page_title=observation.title,
        visible_text_summary=redact_text(observation.visible_text_summary),
        element_inventory=element_inventory_json(observation),
        recent_history="\n".join(recent_history[-8:]) or "(none)",
        feedback_block=feedback_block,
    )
