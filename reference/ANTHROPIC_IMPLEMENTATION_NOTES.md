# Current Anthropic Notes (checked August 2026)

These notes are implementation guidance, not assignment requirements. Verify against current official Anthropic docs if an SDK call signature differs.

- Claude Fable 5 API model ID: `claude-fable-5`.
- Use the native Anthropic Messages API / Python SDK.
- Claude Fable 5 uses adaptive thinking; do not add obsolete manual thinking-token configuration.
- Prefer schema-constrained/strict tool inputs or structured outputs for the discovery action contract when supported by the installed SDK.
- If strict tool use is unavailable in the installed SDK version, validate every proposed action with Pydantic and retry/re-prompt on invalid output; never execute invalid/unparsed free-form text.
- Claude Code reads `CLAUDE.md` as project-level persistent instructions.
- Keep `ANTHROPIC_API_KEY` in environment/.env only; never commit it.

Implementation principle: the LLM proposes a **small structured action**, while application code owns policy checks, element resolution, browser execution, logging, timeout/retry logic, and artifact compilation.
