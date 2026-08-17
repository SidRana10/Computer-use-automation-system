"""Provider selection and Gemini structured-action handling."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from ui_capabilities.config import Settings
from ui_capabilities.discovery.action_tools import InvalidToolCall, parse_tool_call
from ui_capabilities.discovery.providers import ProviderConfigError, create_model_adapter
from ui_capabilities.models.actions import ClickAction, FillAction
from ui_capabilities.policy.redaction import Redactor

REPO = Path(__file__).resolve().parents[2]


def settings(**kwargs) -> Settings:
    return Settings(**kwargs)


# ----------------------------------------------------------- provider factory


def test_gemini_selected_by_default_provider_setting():
    s = settings(gemini_api_key="test-key-not-real")
    adapter = create_model_adapter(s.llm_provider, s, Redactor())
    assert type(adapter).__name__ == "GeminiModelAdapter"
    assert adapter.name == "gemini:gemini-3-flash-preview"


def test_anthropic_remains_available_as_provider():
    s = settings(anthropic_api_key="test-key-not-real")
    adapter = create_model_adapter("anthropic", s, Redactor())
    assert type(adapter).__name__ == "AnthropicModelAdapter"
    assert adapter.name.startswith("anthropic:")


def test_gemini_without_key_fails_loudly():
    with pytest.raises(ProviderConfigError, match="GEMINI_API_KEY"):
        create_model_adapter("gemini", settings(), Redactor())


def test_anthropic_without_key_fails_loudly():
    with pytest.raises(ProviderConfigError, match="ANTHROPIC_API_KEY"):
        create_model_adapter("anthropic", settings(), Redactor())


@pytest.mark.parametrize("name", ["fake", "fake-subaccount", "scripted", "", "gpt"])
def test_factory_never_returns_a_test_double(name):
    with pytest.raises(ProviderConfigError):
        create_model_adapter(name, settings(gemini_api_key="k", anthropic_api_key="k"), Redactor())


# ------------------------------------------------- structured action parsing


def test_parse_tool_call_valid_click():
    action = parse_tool_call("click", {"element_ref": "e2", "rationale_summary": "open accounts"})
    assert isinstance(action, ClickAction)
    assert action.element_ref == "e2"


def test_parse_tool_call_valid_fill_with_input_ref():
    action = parse_tool_call("fill", {"element_ref": "e1", "value_source": {"input_name": "member_id"}})
    assert isinstance(action, FillAction)
    assert action.value_source.input_name == "member_id"


def test_parse_tool_call_rejects_unknown_tool_and_bad_payload():
    with pytest.raises(InvalidToolCall, match="unknown tool"):
        parse_tool_call("run_shell", {"cmd": "rm -rf /"})
    with pytest.raises(InvalidToolCall, match="invalid click"):
        parse_tool_call("click", {})  # neither element_ref nor coordinate


def test_gemini_schema_simplifier_produces_supported_subset():
    from ui_capabilities.discovery.action_tools import ACTION_TOOLS, tool_schema
    from ui_capabilities.discovery.gemini_client import simplify_schema_for_gemini

    for name, cls in ACTION_TOOLS.items():
        simplified = simplify_schema_for_gemini(tool_schema(cls))
        text = str(simplified)
        assert "$ref" not in text, name
        assert "$defs" not in text, name
        assert "prefixItems" not in text, name
        assert "action" not in simplified.get("properties", {}), name


# --------------------------------------------- Gemini adapter behavior (mocked)


class _FakeGeminiClient:
    """Stands in for genai.Client; returns canned function-call responses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0
        self.aio = SimpleNamespace(models=SimpleNamespace(generate_content=self._generate))

    async def _generate(self, *, model, contents, config):
        self.calls += 1
        return self._responses.pop(0)


def _response(name: str, args: dict):
    call = SimpleNamespace(name=name, args=args, id=None)
    content = SimpleNamespace(role="model", parts=[])
    return SimpleNamespace(function_calls=[call], candidates=[SimpleNamespace(content=content)])


def _gemini_adapter(fake_client):
    from ui_capabilities.discovery.gemini_client import GeminiModelAdapter

    adapter = GeminiModelAdapter.__new__(GeminiModelAdapter)
    adapter._client = fake_client
    adapter._model = "gemini-3-flash-preview"
    adapter._redactor = Redactor()
    from ui_capabilities.discovery.gemini_client import build_gemini_tools

    adapter._tools = build_gemini_tools()
    adapter.name = "gemini:test"
    return adapter


def _observation():
    from ui_capabilities.surfaces.base import Observation

    return Observation(url="http://127.0.0.1:8001/", path="/", title="t", visible_text_summary="", elements=[], fingerprint="f")


def _context():
    from ui_capabilities.discovery.model_adapter import TurnContext
    from ui_capabilities.policy.config import default_demo_policy

    return TurnContext(
        goal="g", target_app_name="t", entry_point="http://127.0.0.1:8001/",
        step_number=1, max_steps=20, elapsed_seconds=0, timeout_seconds=180,
        policy=default_demo_policy(),
    )


async def test_gemini_adapter_parses_valid_function_call():
    client = _FakeGeminiClient([_response("click", {"element_ref": "e3", "rationale_summary": "next"})])
    adapter = _gemini_adapter(client)
    action = await adapter.next_action(_observation(), _context())
    assert isinstance(action, ClickAction)
    assert action.element_ref == "e3"
    assert client.calls == 1


async def test_gemini_adapter_retries_once_then_accepts():
    client = _FakeGeminiClient(
        [
            _response("click", {}),  # invalid: no target
            _response("click", {"element_ref": "e1"}),
        ]
    )
    adapter = _gemini_adapter(client)
    action = await adapter.next_action(_observation(), _context())
    assert isinstance(action, ClickAction)
    assert client.calls == 2


async def test_gemini_adapter_rejects_persistently_invalid_output():
    client = _FakeGeminiClient([_response("click", {}), _response("run_shell", {"cmd": "ls"})])
    adapter = _gemini_adapter(client)
    with pytest.raises(ValueError, match="valid structured action"):
        await adapter.next_action(_observation(), _context())
    assert client.calls == 2  # bounded: exactly one retry, never free-form execution


# ------------------------------------------ genuine evidence: no fake fallback


def _load_capture_module():
    spec = importlib.util.spec_from_file_location("capture_evidence", REPO / "scripts" / "capture_evidence.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_capture_evidence_fails_loudly_without_key(monkeypatch):
    capture = _load_capture_module()
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="GEMINI_API_KEY"):
        capture.require_genuine_provider("gemini")
    with pytest.raises(SystemExit, match="ANTHROPIC_API_KEY"):
        capture.require_genuine_provider("anthropic")


def test_capture_evidence_rejects_fake_as_genuine_provider(monkeypatch):
    capture = _load_capture_module()
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    with pytest.raises(SystemExit, match="not a genuine provider"):
        capture.require_genuine_provider("fake")
    # sanity: with the key present, a genuine provider passes the gate
    capture.require_genuine_provider("gemini")
