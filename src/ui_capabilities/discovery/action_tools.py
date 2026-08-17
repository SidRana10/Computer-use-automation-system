"""Provider-neutral definition of the discovery action tool surface.

Every LLM provider adapter exposes exactly these eight narrow UI-action tools
and validates every proposal through `parse_tool_call` before it goes anywhere
near policy or the browser. There is deliberately no shell/JS/code tool, and
no provider may add one.
"""

from __future__ import annotations

from typing import Type

from pydantic import BaseModel, ValidationError

from ..models.actions import (
    ClickAction,
    DiscoveryAction,
    DoneAction,
    ExtractAction,
    FillAction,
    NavigateAction,
    RequestHumanAction,
    SelectAction,
    WaitAction,
)

ACTION_TOOLS: dict[str, Type[BaseModel]] = {
    "navigate": NavigateAction,
    "click": ClickAction,
    "fill": FillAction,
    "select": SelectAction,
    "extract": ExtractAction,
    "wait": WaitAction,
    "done": DoneAction,
    "request_human": RequestHumanAction,
}

TOOL_DESCRIPTIONS = {
    "navigate": "Navigate the browser to a URL inside the allowed target.",
    "click": "Click one interactive element, addressed by its `ref` from INTERACTIVE ELEMENTS.",
    "fill": "Fill a text field. Use value_source.input_name for invocation inputs so the executor binds the real value.",
    "select": "Choose an option in a select control.",
    "extract": "Read the visible text of one element as a named typed output.",
    "wait": "Wait briefly for the UI to settle (bounded by policy).",
    "done": "Declare the goal visibly complete, with a success condition grounded in the current UI.",
    "request_human": "Ask for a human operator when blocked, uncertain, or facing a risky action.",
}


def tool_schema(model_cls: Type[BaseModel]) -> dict:
    """JSON schema for one action tool; the action discriminator is implied by
    the tool name and removed from the schema."""
    schema = model_cls.model_json_schema()
    schema.pop("title", None)
    schema.get("properties", {}).pop("action", None)
    if "required" in schema:
        schema["required"] = [r for r in schema["required"] if r != "action"]
    return schema


class InvalidToolCall(ValueError):
    """The model's proposal did not validate; it is never executed."""


def parse_tool_call(name: str, payload: dict | None) -> DiscoveryAction:
    model_cls = ACTION_TOOLS.get(name)
    if model_cls is None:
        raise InvalidToolCall(f"unknown tool {name!r}")
    data = dict(payload or {})
    data["action"] = name
    try:
        return model_cls.model_validate(data)  # type: ignore[return-value]
    except ValidationError as exc:
        raise InvalidToolCall(f"invalid {name} payload: {exc.errors()[:3]}") from exc
