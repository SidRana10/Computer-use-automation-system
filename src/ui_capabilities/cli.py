"""`uicap` console entry point.

Commands:
  uicap demo-app   — run the synthetic target application
  uicap discover   — LLM (or scripted test-double) discovery -> capability artifact
  uicap replay     — deterministic, LLM-free replay of a saved artifact
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from .config import Settings
from .discovery.agent import DiscoveryAgent
from .discovery.compiler import ArtifactCompiler, load_artifact, save_artifact
from .discovery.fake_model import ScriptedBalanceModel, ScriptedSubAccountModel
from .discovery.profiles import demo_app_error_rules
from .models.artifact import InputSpec
from .models.errors import CompileError
from .observability.evidence import EvidenceManager
from .observability.logger import RunLogger
from .policy.config import default_demo_policy
from .policy.engine import PolicyEngine
from .policy.redaction import Redactor
from .replay.engine import ReplayEngine
from .surfaces.playwright_web import PlaywrightWebSurface

KNOWN_INPUT_SPECS: dict[str, InputSpec] = {
    "member_id": InputSpec(
        name="member_id",
        type="string",
        sensitive=True,
        pattern=r"M-\d{5}",
        description="Member identifier in the demo format M-#####",
    ),
    "account_type": InputSpec(
        name="account_type",
        type="string",
        description="Sub-account product type as shown in the console",
    ),
}

EXIT_BY_STATUS = {"success": 0, "business_outcome": 0, "failure": 2, "escalated": 3}


def _parse_inputs(pairs: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"--input must be name=value, got {pair!r}")
        name, _, value = pair.partition("=")
        out[name.strip()] = value.strip()
    return out


def _input_specs_for(names: list[str], redactor: Redactor) -> list[InputSpec]:
    specs = []
    for name in names:
        if name in KNOWN_INPUT_SPECS:
            specs.append(KNOWN_INPUT_SPECS[name])
        else:
            specs.append(
                InputSpec(
                    name=name,
                    type="string",
                    sensitive=redactor.is_sensitive_key(name),
                    description=f"Invocation input {name}",
                )
            )
    return specs


def _post_demo_config(target_base: str, params: dict[str, str]) -> None:
    query = urllib.parse.urlencode(params)
    url = f"{target_base.rstrip('/')}/demo/config?{query}"
    request = urllib.request.Request(url, method="POST")
    with urllib.request.urlopen(request, timeout=10) as response:  # local demo tooling only
        response.read()


async def _build_handoff(settings: Settings, surface, logger, redactor, evidence, enable_operator: bool):
    from .handoff.manager import HandoffManager
    from .handoff.operator_app import OperatorServer, create_operator_app
    from .handoff.store import InterventionStore

    store = InterventionStore(dump_path=evidence.run_dir / "interventions.json")
    manager = HandoffManager(
        store=store,
        surface=surface,
        logger=logger,
        redactor=redactor,
        operator_base_url=settings.operator_base_url,
    )
    server = None
    if enable_operator:
        parsed = urllib.parse.urlparse(settings.operator_base_url)
        server = OperatorServer(create_operator_app(manager), parsed.hostname or "127.0.0.1", parsed.port or 8002)
        await server.start()
        print(f"operator console: {settings.operator_base_url}")
    return manager, server


# ---------------------------------------------------------------- discover


async def _discover(args: argparse.Namespace) -> int:
    settings = Settings.load()
    inputs = _parse_inputs(args.input or [])
    run_id = f"disc-{uuid.uuid4().hex[:10]}"
    evidence = EvidenceManager(settings.evidence_dir, run_id)
    redactor = Redactor()
    logger = RunLogger(evidence.log_path, redactor, run_id)
    policy = PolicyEngine(default_demo_policy(args.target))
    input_specs = _input_specs_for(sorted(inputs.keys()), redactor)

    # Genuine providers go through the factory (fails loudly on missing keys);
    # scripted test doubles must be requested explicitly by name and are never
    # a fallback for genuine discovery.
    adapter_name = args.model_adapter or settings.llm_provider
    if adapter_name == "fake":
        model = ScriptedBalanceModel()
        print("WARNING: scripted fake model adapter (test double) — output is not valid discovery evidence")
    elif adapter_name == "fake-subaccount":
        model = ScriptedSubAccountModel()
        print("WARNING: scripted fake-subaccount model adapter (test double) — not valid discovery evidence")
    else:
        from .discovery.providers import ProviderConfigError, create_model_adapter, provider_model_name

        try:
            model = create_model_adapter(adapter_name, settings, redactor)
        except ProviderConfigError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(f"discovery provider: {adapter_name} (model: {provider_model_name(adapter_name, settings)})")

    surface = PlaywrightWebSurface(settings, evidence, headless=args.headless or None)
    handoff = None
    server = None
    try:
        await surface.start(args.target)
        await surface.start_trace()
        if not args.no_operator:
            handoff, server = await _build_handoff(settings, surface, logger, redactor, evidence, True)
        agent = DiscoveryAgent(
            surface=surface,
            model=model,
            policy=policy,
            settings=settings,
            logger=logger,
            evidence=evidence,
            redactor=redactor,
            handoff=handoff,
        )
        outcome = await agent.run(
            goal=args.goal,
            entry_point=args.target,
            capability_id=args.capability_id,
            input_specs=input_specs,
            input_bindings=inputs,
            target_app_name="Northstar Credit Union — Member Servicing Console (Demo)",
        )
        await surface.stop_trace()

        print(f"\ndiscovery status: {outcome.status}")
        print(f"evidence: {evidence.run_dir}")
        if outcome.status != "success":
            print(f"reason: {outcome.reason}")
            return 2 if outcome.status == "failed" else 3

        compiler = ArtifactCompiler(policy, error_rules_factory=demo_app_error_rules)
        try:
            artifact = compiler.compile(outcome.run)
        except CompileError as exc:
            print(f"artifact compilation failed: {exc}", file=sys.stderr)
            return 2
        output = Path(args.output or settings.artifact_dir / f"{args.capability_id}.v1.json")
        save_artifact(artifact, output)
        print(f"steps recorded: {len(outcome.run.steps)}, compiled: {len(artifact.steps)}")
        print(f"artifact: {output}")
        return 0
    finally:
        if server is not None:
            await server.stop()
        await surface.close()


# ------------------------------------------------------------------ replay


async def _replay(args: argparse.Namespace) -> int:
    settings = Settings.load()
    artifact = load_artifact(args.artifact)
    inputs = _parse_inputs(args.input or [])
    run_id = f"rep-{uuid.uuid4().hex[:10]}"
    evidence = EvidenceManager(settings.evidence_dir, run_id)
    redactor = Redactor()
    logger = RunLogger(evidence.log_path, redactor, run_id)
    policy = PolicyEngine(default_demo_policy(artifact.target.entry_point))

    origin = artifact.target.entry_point
    demo_params: dict[str, str] = {}
    if args.demo_failure:
        demo_params["failure"] = args.demo_failure
    if args.demo_interstitial:
        demo_params["interstitial"] = "true"
    if args.demo_slow:
        demo_params["slow_accounts"] = "true"
    if args.demo_session_expired:
        demo_params["session_expired"] = "true"
    if demo_params:
        parsed = urllib.parse.urlparse(origin)
        _post_demo_config(f"{parsed.scheme}://{parsed.netloc}", demo_params)
        print(f"demo knobs set: {demo_params} (injected simulation for evidence)")

    surface = PlaywrightWebSurface(settings, evidence, headless=args.headless or None)
    handoff = None
    server = None
    try:
        if not args.no_operator:
            handoff, server = await _build_handoff(settings, surface, logger, redactor, evidence, True)
        engine = ReplayEngine(
            surface=surface,
            global_policy=policy,
            settings=settings,
            logger=logger,
            evidence=evidence,
            redactor=redactor,
            handoff=handoff,
        )
        result = await engine.replay(artifact, inputs)
        payload = result.model_dump()
        print("\n=== replay result ===")
        print(json.dumps(payload, indent=2, default=str))
        print(f"evidence: {evidence.run_dir}")
        return EXIT_BY_STATUS.get(result.status, 2)
    finally:
        if server is not None:
            await server.stop()
        await surface.close()


# ------------------------------------------------------------------- parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uicap", description="UI capabilities: discover once, replay deterministically.")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo-app", help="run the synthetic Northstar demo target app")
    demo.add_argument("--host", default="127.0.0.1")
    demo.add_argument("--port", type=int, default=8001)

    disc = sub.add_parser("discover", help="discover a capability from a natural-language goal")
    disc.add_argument("--goal", required=True)
    disc.add_argument("--target", required=True, help="entry point URL of the target app")
    disc.add_argument("--capability-id", required=True)
    disc.add_argument("--input", action="append", metavar="NAME=VALUE", help="invocation input binding (repeatable)")
    disc.add_argument("--output", help="artifact output path (default artifacts/<capability_id>.v1.json)")
    disc.add_argument(
        "--model-adapter",
        choices=["gemini", "anthropic", "fake", "fake-subaccount"],
        default=None,
        help="LLM provider for discovery (default: LLM_PROVIDER env, gemini). "
        "'fake*' are offline test doubles, never valid as genuine evidence.",
    )
    disc.add_argument("--headless", action="store_true")
    disc.add_argument("--no-operator", action="store_true", help="skip the in-process operator console")

    rep = sub.add_parser("replay", help="deterministically replay a saved artifact (no LLM)")
    rep.add_argument("--artifact", required=True)
    rep.add_argument("--input", action="append", metavar="NAME=VALUE")
    rep.add_argument("--headless", action="store_true")
    rep.add_argument("--no-operator", action="store_true")
    rep.add_argument("--demo-failure", choices=["missing_accounts_control"], help="deterministic injected hard failure (demo evidence)")
    rep.add_argument("--demo-interstitial", action="store_true", help="arm the known idle interstitial (recoverable demo)")
    rep.add_argument("--demo-slow", action="store_true", help="arm the transient slow-load state (recoverable demo)")
    rep.add_argument("--demo-session-expired", action="store_true", help="arm the session-expired state (hard failure demo)")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "demo-app":
        import uvicorn

        sys.path.insert(0, str(Path.cwd()))
        uvicorn.run("demo_app.app:app", host=args.host, port=args.port, log_level="info")
        return
    if args.command == "discover":
        raise SystemExit(asyncio.run(_discover(args)))
    if args.command == "replay":
        raise SystemExit(asyncio.run(_replay(args)))


if __name__ == "__main__":
    main()
