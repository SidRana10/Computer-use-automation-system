"""Google Gemini adapter for genuine discovery (default provider).

Uses the official `google-genai` SDK with forced function calling: the model
must call exactly one of the eight narrow UI-action tools per turn, and every
proposal is Pydantic-validated (`parse_tool_call`) before it goes anywhere
near policy or the browser. The screenshot is attached as an image part every
turn, so the run remains genuine computer-use against the live surface. There
is deliberately no code/JS/shell tool.
"""

from __future__ import annotations

import asyncio
import re

from pathlib import Path

from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError

from ..models.actions import DiscoveryAction
from ..policy.redaction import Redactor
from ..surfaces.base import Observation
from .action_tools import ACTION_TOOLS, TOOL_DESCRIPTIONS, InvalidToolCall, parse_tool_call, tool_schema
from .model_adapter import TurnContext
from .prompts import SYSTEM_PROMPT, build_turn_prompt

DEFAULT_GEMINI_MODEL = "gemini-3-flash-preview"

# Bounded backoff for transient provider failures: the free-tier per-minute
# rate limit (429, observed: 5 requests/minute/model) and a transient
# "experiencing high demand" 503, both observed live. A multi-turn discovery
# run makes one call per step, so an unhandled transient failure mid-run would
# otherwise crash a genuine discovery session outright. Retries only these two
# specific, known-transient conditions; every other error still propagates
# immediately.
_MAX_RATE_LIMIT_RETRIES = 4
_DEFAULT_RETRY_DELAY_S = 20.0
_SERVER_ERROR_RETRY_DELAY_S = 15.0
_RETRY_DELAY_RE = re.compile(r"'retryDelay':\s*'(\d+(?:\.\d+)?)s'")

# Proactive pacing floor: observed live at 5 requests/minute/model, so an
# average spacing of 12s stays exactly at the limit — 13s leaves margin.
# Cheaper than discovering the cap reactively every run: a burst of calls
# that clears in under a second (page loads are sometimes that fast) would
# otherwise immediately trip a 429 and fall into the escalating backoff below.
_MIN_CALL_INTERVAL_S = 13.0


def _retry_delay_seconds(exc: ClientError) -> float:
    match = _RETRY_DELAY_RE.search(str(exc))
    return float(match.group(1)) + 1.0 if match else _DEFAULT_RETRY_DELAY_S


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
        self._last_call_at: float | None = None

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
            response = await self._generate_with_backoff(contents, config)
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

    async def _generate_with_backoff(self, contents: list[types.Content], config: types.GenerateContentConfig):
        for attempt in range(_MAX_RATE_LIMIT_RETRIES + 1):
            await self._wait_for_pacing_floor()
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config,
                )
                self._last_call_at = asyncio.get_event_loop().time()
                return response
            except ClientError as exc:
                self._last_call_at = asyncio.get_event_loop().time()
                if exc.code != 429 or attempt == _MAX_RATE_LIMIT_RETRIES:
                    raise
                await asyncio.sleep(_retry_delay_seconds(exc))
            except ServerError as exc:
                self._last_call_at = asyncio.get_event_loop().time()
                if exc.code != 503 or attempt == _MAX_RATE_LIMIT_RETRIES:
                    raise
                await asyncio.sleep(_SERVER_ERROR_RETRY_DELAY_S)

    async def _wait_for_pacing_floor(self) -> None:
        if self._last_call_at is None:
            return
        elapsed = asyncio.get_event_loop().time() - self._last_call_at
        remaining = _MIN_CALL_INTERVAL_S - elapsed
        if remaining > 0:
            await asyncio.sleep(remaining)
