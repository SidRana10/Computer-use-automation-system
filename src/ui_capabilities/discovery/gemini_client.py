"""Google Gemini adapter for genuine discovery (default provider).

Uses the official `google-genai` SDK with forced function calling: the model
must call exactly one of the eight narrow UI-action tools per turn, and every
proposal is Pydantic-validated (`parse_tool_call`) before it goes anywhere
near policy or the browser. The screenshot is attached as an image part every
turn, so the run remains genuine computer-use against the live surface. There
is deliberately no code/JS/shell tool.
"""

from __future__ import annotations

from pathlib import Path

from google import genai
from google.genai import types

from ..models.actions import DiscoveryAction
from ..policy.redaction import Redactor
from ..surfaces.base import Observation
from .action_tools import ACTION_TOOLS, TOOL_DESCRIPTIONS, InvalidToolCall, parse_tool_call, tool_schema
from .model_adapter import TurnContext
from .prompts import SYSTEM_PROMPT, build_turn_prompt

DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"


def simplify_schema_for_gemini(schema: dict) -> dict:
    """Normalize a Pydantic JSON schema to the subset Gemini's function
    declarations accept reliably: inline $defs/$ref, collapse
    `anyOf [T, null]` to nullable T, and flatten tuple `prefixItems`."""
    defs = schema.get("$defs", {})

    def resolve(node):
        if isinstance(node, list):
            return [resolve(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            ref_name = node["$ref"].split("/")[-1]
            target = dict(defs.get(ref_name, {}))
            merged = {**target, **{k: v for k, v in node.items() if k != "$ref"}}
            return resolve(merged)
        node = {k: resolve(v) for k, v in node.items() if k not in ("title", "$defs")}
        if "anyOf" in node:
            options = [o for o in node["anyOf"] if not (isinstance(o, dict) and o.get("type") == "null")]
            nullable = len(options) < len(node["anyOf"])
            if len(options) == 1:
                base = options[0] if isinstance(options[0], dict) else {}
                rest = {k: v for k, v in node.items() if k != "anyOf"}
                node = {**base, **rest}
                if nullable:
                    node["nullable"] = True
            else:
                node["anyOf"] = options
        if "prefixItems" in node:
            items = node.pop("prefixItems")
            node.setdefault("items", items[0] if items else {"type": "number"})
        if "const" in node:
            node["enum"] = [node.pop("const")]
        return node

    return resolve(schema)


def build_gemini_tools() -> list[types.Tool]:
    declarations = [
        types.FunctionDeclaration(
            name=name,
            description=TOOL_DESCRIPTIONS[name],
            parameters_json_schema=simplify_schema_for_gemini(tool_schema(cls)),
        )
        for name, cls in ACTION_TOOLS.items()
    ]
    return [types.Tool(function_declarations=declarations)]


class GeminiModelAdapter:
    name = "gemini"

    def __init__(self, api_key: str, model: str, redactor: Redactor):
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._redactor = redactor
        self._tools = build_gemini_tools()
        self.name = f"gemini:{model}"  # flows into artifact provenance

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
        parts: list[types.Part] = [types.Part.from_text(text=prompt)]
        if observation.screenshot_path and Path(observation.screenshot_path).exists():
            parts.append(
                types.Part.from_bytes(
                    data=Path(observation.screenshot_path).read_bytes(),
                    mime_type="image/png",
                )
            )
        contents: list[types.Content] = [types.Content(role="user", parts=parts)]

        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=self._tools,
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="ANY")
            ),
            temperature=0.0,
        )

        last_error: str | None = None
        for _attempt in range(2):
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=config,
            )
            calls = response.function_calls or []
            if not calls:
                raise ValueError("model failed to produce a structured action: no function call in response")
            call = calls[0]
            try:
                return parse_tool_call(call.name or "", dict(call.args or {}))
            except InvalidToolCall as exc:
                last_error = str(exc)
            # One bounded re-prompt carrying the validation error back as a
            # function response; invalid output is never executed.
            model_content = (
                response.candidates[0].content
                if response.candidates and response.candidates[0].content
                else types.Content(role="model", parts=[types.Part(function_call=call)])
            )
            contents = contents + [
                model_content,
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(
                            name=call.name or "unknown",
                            response={"error": f"Rejected: {last_error}. Return one valid structured action."},
                        )
                    ],
                ),
            ]
        raise ValueError(f"model failed to produce a valid structured action: {last_error}")
