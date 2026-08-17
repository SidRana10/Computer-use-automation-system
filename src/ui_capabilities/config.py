"""Central runtime configuration.

All timeouts, retry budgets, model selection, and paths live here so the rest
of the system never reads environment variables directly.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel


class Settings(BaseModel):
    # LLM provider for genuine discovery: "gemini" (default) or "anthropic".
    # Replay never reads any of these — it is LLM-free by construction.
    llm_provider: str = "gemini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3-flash-preview"
    anthropic_api_key: str | None = None
    discovery_model: str = "claude-fable-5"  # anthropic provider model
    target_base_url: str = "http://127.0.0.1:8001"
    operator_base_url: str = "http://127.0.0.1:8002"
    playwright_headless: bool = False

    max_discovery_steps: int = 20
    discovery_timeout_seconds: int = 180
    default_step_timeout_ms: int = 5000
    condition_poll_interval_ms: int = 200
    max_wait_action_ms: int = 3000
    max_recovery_attempts: int = 2
    max_repeated_states: int = 3
    max_policy_denials: int = 3
    max_execution_errors: int = 3

    evidence_dir: Path = Path("evidence")
    artifact_dir: Path = Path("artifacts")
    log_level: str = "INFO"

    @classmethod
    def load(cls, env_file: str | os.PathLike[str] = ".env") -> "Settings":
        """Build settings from process env, optionally overlaying a .env file."""
        load_dotenv(env_file, override=False)
        env = os.environ

        def _bool(name: str, default: bool) -> bool:
            raw = env.get(name)
            if raw is None:
                return default
            return raw.strip().lower() in {"1", "true", "yes", "on"}

        def _int(name: str, default: int) -> int:
            raw = env.get(name)
            return int(raw) if raw not in (None, "") else default

        return cls(
            llm_provider=(env.get("LLM_PROVIDER") or "gemini").strip().lower(),
            gemini_api_key=env.get("GEMINI_API_KEY") or None,
            gemini_model=env.get("GEMINI_MODEL") or "gemini-3-flash-preview",
            anthropic_api_key=env.get("ANTHROPIC_API_KEY") or None,
            discovery_model=env.get("DISCOVERY_MODEL") or "claude-fable-5",
            target_base_url=env.get("TARGET_BASE_URL") or "http://127.0.0.1:8001",
            operator_base_url=env.get("OPERATOR_BASE_URL") or "http://127.0.0.1:8002",
            playwright_headless=_bool("PLAYWRIGHT_HEADLESS", False),
            max_discovery_steps=_int("MAX_DISCOVERY_STEPS", 20),
            discovery_timeout_seconds=_int("DISCOVERY_TIMEOUT_SECONDS", 180),
            default_step_timeout_ms=_int("DEFAULT_STEP_TIMEOUT_MS", 5000),
            max_recovery_attempts=_int("MAX_RECOVERY_ATTEMPTS", 2),
            evidence_dir=Path(env.get("EVIDENCE_DIR") or "evidence"),
            artifact_dir=Path(env.get("ARTIFACT_DIR") or "artifacts"),
            log_level=env.get("LOG_LEVEL") or "INFO",
        )
