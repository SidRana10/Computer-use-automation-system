"""Anthropic Messages API adapter for genuine discovery (optional provider).

Each discovery action type is exposed as one narrow tool; the model must call
exactly one per turn. Every proposal is Pydantic-validated before it goes
anywhere near policy or the browser. There is deliberately no code/JS/shell
tool.
"""

from __future__ import annotations

import base64
from pathlib import Path

from anthropic import AsyncAnthropic

from ..models.actions import DiscoveryAction
from ..policy.redaction import Redactor
from ..surfaces.base import Observation
from .action_tools import ACTION_TOOLS, TOOL_DESCRIPTIONS, InvalidToolCall, parse_tool_call, tool_schema
from .model_adapter import TurnContext
from .prompts import SYSTEM_PROMPT, build_turn_prompt


def build_tools() -> list[dict]:
    return [
        {
            "name": name,
            "description": TOOL_DESCRIPTIONS[name],
            "input_schema": tool_schema(cls),
        }
        for name, cls in ACTION_TOOLS.items()
    ]


class AnthropicModelAdapter:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, redactor: Redactor):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._redactor = redactor
        self._tools = build_tools()
        self.name = f"anthropic:{model}"  # flows into artifact provenance

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
                raise ValueError("model failed to produce a structured action: no tool_use block in response")
            try:
                return parse_tool_call(tool_use.name, dict(tool_use.input or {}))
            except InvalidToolCall as exc:
                last_error = str(exc)
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
