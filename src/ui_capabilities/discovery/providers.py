"""LLM provider selection for genuine discovery.

`create_model_adapter` is the only way a genuine provider is constructed. It
knows exactly two providers — gemini (default) and anthropic — and fails
loudly when the required API key is absent. It can NEVER return a scripted
test double: fakes are constructed only where the caller explicitly asks for
one by name, and they are excluded from genuine evidence by design.
"""

from __future__ import annotations

from ..config import Settings
from ..models.errors import CapabilityError
from ..policy.redaction import Redactor
from .model_adapter import ModelAdapter

GENUINE_PROVIDERS = ("gemini", "anthropic")


class ProviderConfigError(CapabilityError):
    """Provider misconfiguration (unknown provider or missing credentials)."""


def create_model_adapter(provider: str, settings: Settings, redactor: Redactor) -> ModelAdapter:
    """Build a genuine LLM provider adapter, failing loudly on misconfiguration.

    Test doubles ('fake', 'fake-subaccount') are intentionally NOT accepted
    here — genuine discovery must never silently fall back to a script.
    """
    normalized = (provider or "").strip().lower()
    if normalized == "gemini":
        if not settings.gemini_api_key:
            raise ProviderConfigError(
                "GEMINI_API_KEY is not set. Set it in the environment or .env for genuine Gemini discovery "
                "(free tier: https://aistudio.google.com/apikey), or select LLM_PROVIDER=anthropic."
            )
        from .gemini_client import GeminiModelAdapter

        return GeminiModelAdapter(settings.gemini_api_key, settings.gemini_model, redactor)
    if normalized == "anthropic":
        if not settings.anthropic_api_key:
            raise ProviderConfigError(
                "ANTHROPIC_API_KEY is not set. Set it in the environment or .env for Anthropic discovery, "
                "or use the default LLM_PROVIDER=gemini."
            )
        from .anthropic_client import AnthropicModelAdapter

        return AnthropicModelAdapter(settings.anthropic_api_key, settings.discovery_model, redactor)
    raise ProviderConfigError(
        f"unknown LLM provider {provider!r}: genuine discovery supports {list(GENUINE_PROVIDERS)} "
        "(scripted test doubles are not genuine providers and must be requested explicitly via the CLI)"
    )


def provider_model_name(provider: str, settings: Settings) -> str:
    if provider == "gemini":
        return settings.gemini_model
    return settings.discovery_model
