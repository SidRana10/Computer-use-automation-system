"""Anthropic Messages API adapter for genuine discovery.

Each discovery action type is exposed as one narrow tool; the model must call
exactly one per turn. Every proposal is Pydantic-validated before it goes
anywhere near policy or the browser. There is deliberately no code/JS/shell
tool.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Type

from anthropic import AsyncAnthropic
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
from ..policy.redaction import Redactor
from ..surfaces.base import Observation
from .model_adapter import TurnContext
from .prompts import SYSTEM_PROMPT, build_turn_prompt

_ACTION_TOOLS: dict[str, Type[BaseModel]] = {
    "navigate": NavigateAction,
    "click": ClickAction,
    "fill": FillAction,
    "select": SelectAction,
    "extract": ExtractAction,
    "wait": WaitAction,
    "done": DoneAction,
    "request_human": RequestHumanAction,
}

_TOOL_DESCRIPTIONS = {
    "navigate": "Navigate the browser to a URL inside the allowed target.",
    "click": "Click one interactive element, addressed by its `ref` from INTERACTIVE ELEMENTS.",
    "fill": "Fill a text field. Use value_source.input_name for invocation inputs so the executor binds the real value.",
    "select": "Choose an option in a select control.",
    "extract": "Read the visible text of one element as a named typed output.",
    "wait": "Wait briefly for the UI to settle (bounded by policy).",
    "done": "Declare the goal visibly complete, with a success condition grounded in the current UI.",
    "request_human": "Ask for a human operator when blocked, uncertain, or facing a risky action.",
}


def _tool_schema(model_cls: Type[BaseModel]) -> dict:
    schema = model_cls.model_json_schema()
    schema.pop("title", None)
    # The action discriminator is implied by the tool name.
    schema.get("properties", {}).pop("action", None)
    if "required" in schema:
        schema["required"] = [r for r in schema["required"] if r != "action"]
    return schema


def build_tools() -> list[dict]:
    return [
        {
            "name": name,
            "description": _TOOL_DESCRIPTIONS[name],
            "input_schema": _tool_schema(cls),
        }
        for name, cls in _ACTION_TOOLS.items()
    ]


class AnthropicModelAdapter:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, redactor: Redactor):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._redactor = redactor
        self._tools = build_tools()

    async def next_action(self, observation: Observation, context: TurnContext) -> DiscoveryAction:
        prompt = build_turn_prompt(
            goal=context.goal,
            target_app_name=context.target_app_name,
            entry_point=context.entry_point,
            observation=observation,
            step_number=context.step_number,
            max_steps=context.max_steps,
            elapsed_seconds=context.elapsed_seconds,
            timeout_seconds=context.timeout_seconds,
            policy=context.policy,
            input_specs=context.input_specs,
            recent_history=context.recent_history,
            feedback=context.feedback,
            redact_text=self._redactor.redact_text,
        )
        content: list[dict] = [{"type": "text", "text": prompt}]
        if observation.screenshot_path and Path(observation.screenshot_path).exists():
            data = base64.standard_b64encode(Path(observation.screenshot_path).read_bytes()).decode()
            content.append(
                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": data}}
            )

        messages: list[dict] = [{"role": "user", "content": content}]
        last_error: str | None = None
        for _attempt in range(2):
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=self._tools,
                tool_choice={"type": "any"},
                messages=messages,
            )
            tool_use = next((b for b in response.content if b.type == "tool_use"), None)
            if tool_use is None:
                last_error = "no tool_use block in response"
                raise ValueError(f"model failed to produce a structured action: {last_error}")
            model_cls = _ACTION_TOOLS.get(tool_use.name)
            if model_cls is None:
                last_error = f"unknown tool {tool_use.name!r}"
            else:
                try:
                    payload = dict(tool_use.input or {})
                    payload["action"] = tool_use.name
                    return model_cls.model_validate(payload)  # type: ignore[return-value]
                except ValidationError as exc:
                    last_error = f"invalid {tool_use.name} payload: {exc.errors()[:3]}"
            # One bounded re-prompt carrying the validation error back as a
            # tool_result; invalid output is never executed.
            messages = messages + [
                {"role": "assistant", "content": response.content},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": f"Rejected: {last_error}. Return one valid structured action.",
                            "is_error": True,
                        }
                    ],
                },
            ]
        raise ValueError(f"model failed to produce a valid structured action: {last_error}")
