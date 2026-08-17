"""Architectural guarantee: the replay path has no model-client dependency.

This is enforced by construction (ReplayEngine takes no model adapter) and
checked here statically: nothing under ui_capabilities/replay, surfaces,
policy, handoff, or observability may reference the anthropic SDK or the
discovery model adapters.
"""

import sys
from pathlib import Path

import ui_capabilities

PACKAGE_ROOT = Path(ui_capabilities.__file__).parent
LLM_FREE_PACKAGES = ["replay", "surfaces", "policy", "handoff", "observability", "models"]
FORBIDDEN_TOKENS = [
    "anthropic",
    "AnthropicModelAdapter",
    "messages.create",
    "genai",
    "gemini",
    "GeminiModelAdapter",
    "generate_content",
]


def test_replay_and_support_packages_never_reference_a_model_client():
    for package in LLM_FREE_PACKAGES:
        for path in (PACKAGE_ROOT / package).rglob("*.py"):
            source = path.read_text()
            for token in FORBIDDEN_TOKENS:
                assert token not in source, f"{path} references {token!r} — replay must be LLM-free"


def test_replay_engine_constructor_has_no_model_parameter():
    from ui_capabilities.replay.engine import ReplayEngine
    import inspect

    params = inspect.signature(ReplayEngine.__init__).parameters
    assert "model" not in params and "model_adapter" not in params


def test_importing_replay_does_not_import_any_llm_sdk():
    for mod in list(sys.modules):
        if mod.startswith("anthropic") or mod.startswith("google.genai") or mod == "google":
            del sys.modules[mod]
    import importlib

    import ui_capabilities.replay.engine as engine

    importlib.reload(engine)
    assert not any(m.startswith("anthropic") for m in sys.modules), "importing the replay engine pulled in the anthropic SDK"
    assert not any(m.startswith("google.genai") for m in sys.modules), "importing the replay engine pulled in the google-genai SDK"
