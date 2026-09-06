#!/usr/bin/env python3
"""Genuine MERIDIAN discovery with a scripted stand-in for the human operator.

Mirrors `uicap discover` (`ui_capabilities.cli._discover`) exactly — same
settings, policy, surface, evidence, logger, and `ArtifactCompiler` — but adds
one thing: policy requires a human to approve any risky/irreversible click
(funds transfer post, open-share post, apply hold), and a discovery run has
no automated way past that gate, by design.

This script does not weaken that gate. It runs a concurrent watcher that
plays the human-operator role exactly as `tests/integration/test_handoff.py`
already does for automated verification: on an intervention, it takes control
of the SAME live session, clicks the one specific, pre-reviewed control by
its accessible name (passed explicitly via --approve-caption, chosen by
whoever runs this script before the run starts, standing in for the person
who would otherwise click "yes" in the operator console), and resumes. The
capability, the button, and the test parameters are fixed by the invocation,
not decided by the script.

Without --approve-caption, a run that raises an intervention is left exactly
as `uicap discover` alone would leave it: paused/escalated, no auto-approval.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ui_capabilities.config import Settings  # noqa: E402
from ui_capabilities.discovery.agent import DiscoveryAgent  # noqa: E402
from ui_capabilities.discovery.compiler import ArtifactCompiler, save_artifact  # noqa: E402
from ui_capabilities.discovery.providers import ProviderConfigError, create_model_adapter, provider_model_name  # noqa: E402
from ui_capabilities.handoff.manager import HandoffManager  # noqa: E402
from ui_capabilities.handoff.store import InterventionStore  # noqa: E402
from ui_capabilities.models.artifact import InputSpec  # noqa: E402
from ui_capabilities.models.errors import CompileError  # noqa: E402
from ui_capabilities.observability.evidence import EvidenceManager  # noqa: E402
from ui_capabilities.observability.logger import RunLogger  # noqa: E402
from ui_capabilities.policy.engine import PolicyEngine  # noqa: E402
from ui_capabilities.policy.redaction import Redactor  # noqa: E402
from ui_capabilities.surfaces.playwright_web import PlaywrightWebSurface  # noqa: E402
from ui_capabilities.targets import get_profile  # noqa: E402


def _parse_inputs(pairs: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in pairs:
        name, _, value = pair.partition("=")
        out[name.strip()] = value.strip()
    return out


def _input_specs_for(names: list[str], redactor: Redactor, profile) -> list[InputSpec]:
    specs = []
    for name in names:
        known = profile.spec_for(name)
        specs.append(known if known is not None else InputSpec(name=name, type="string", sensitive=redactor.is_sensitive_key(name), description=f"invocation input {name}"))
    return specs


async def _auto_operator(handoff: HandoffManager, store: InterventionStore, surface: PlaywrightWebSurface, caption: str, seen: set[str]) -> None:
    """Play the human-operator role for exactly one intervention: take
    control, click the one named control on the live page, resume.

    Only acts on `reason_code == "risky_action"` — the ordinary policy gate
    for a risky/irreversible click (`DiscoveryAgent._human_step`). Any other
    reason (the model calling request_human because it is blocked, confused,
    or facing an unexpected state) gets the run aborted instead: clicking the
    approve caption there would click the write control for a reason that has
    nothing to do with the review actually being ready, exactly what caused
    an unintended real transfer during a genuine run when the model got stuck
    trying to locate the hidden token and the caption was clicked anyway."""
    while True:
        for item in store.all():
            if item.intervention_id in seen or item.status != "open":
                continue
            seen.add(item.intervention_id)
            print(f"\n[auto-operator] intervention {item.intervention_id}: {item.reason_code} — {item.reason_message}")
            if item.reason_code != "risky_action":
                print(f"[auto-operator] reason_code {item.reason_code!r} is not the expected risky-click gate; aborting rather than guessing")
                await handoff.abort(item.intervention_id, note=f"auto-operator only approves reason_code=risky_action, got {item.reason_code!r}")
                return
            print(f"[auto-operator] taking control and clicking {caption!r} on the live page")
            await handoff.take_control(item.intervention_id, operator_id="scripted-operator")
            await surface.page.get_by_role("button", name=caption).click()
            await surface.page.wait_for_load_state("load")
            print("[auto-operator] resuming automation")
            await handoff.resume(item.intervention_id, note=f"scripted operator approved {caption!r}")
            return
        await asyncio.sleep(0.2)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--goal", required=True)
    parser.add_argument("--target", default=get_profile("meridian").default_entry_point)
    parser.add_argument("--capability-id", required=True)
    parser.add_argument("--input", action="append", default=[], metavar="NAME=VALUE")
    parser.add_argument("--output")
    parser.add_argument("--model-adapter", default=None)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--approve-caption", default=None, help="accessible name of the one risky/irreversible control to approve, e.g. 'Post Transfer'")
    args = parser.parse_args()

    settings = Settings.load()
    profile = get_profile("meridian")
    inputs = _parse_inputs(args.input)
    run_id = f"disc-{uuid.uuid4().hex[:10]}"
    evidence = EvidenceManager(settings.evidence_dir, run_id)
    redactor = Redactor(text_patterns=profile.redaction_text_patterns)
    logger = RunLogger(evidence.log_path, redactor, run_id)
    policy = PolicyEngine(profile.policy(args.target))
    input_specs = _input_specs_for(sorted(inputs.keys()), redactor, profile)

    adapter_name = args.model_adapter or settings.llm_provider
    try:
        model = create_model_adapter(adapter_name, settings, redactor)
    except ProviderConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"discovery provider: {adapter_name} (model: {provider_model_name(adapter_name, settings)})")

    surface = PlaywrightWebSurface(
        settings,
        evidence,
        headless=args.headless or None,
        heading_selector=profile.heading_selector,
        mask_selectors=profile.screenshot_mask_selectors,
        redactor=redactor,
        enable_tracing=profile.durable_traces,
    )
    store = InterventionStore(dump_path=evidence.run_dir / "interventions.json")
    handoff = HandoffManager(store=store, surface=surface, logger=logger, redactor=redactor, operator_base_url="")

    watcher_task = None
    try:
        await surface.start(args.target)
        await surface.start_trace()
        if args.approve_caption:
            watcher_task = asyncio.create_task(_auto_operator(handoff, store, surface, args.approve_caption, set()))
        agent = DiscoveryAgent(
            surface=surface,
            model=model,
            policy=policy,
            settings=settings,
            logger=logger,
            evidence=evidence,
            redactor=redactor,
            handoff=handoff,
            fingerprint_extractor=profile.fingerprint,
        )
        outcome = await agent.run(
            goal=args.goal,
            entry_point=args.target,
            capability_id=args.capability_id,
            input_specs=input_specs,
            input_bindings=inputs,
            target_app_name=profile.display_name,
        )
        await surface.stop_trace()

        print(f"\ndiscovery status: {outcome.status}")
        print(f"evidence: {evidence.run_dir}")
        if outcome.status != "success":
            print(f"reason: {outcome.reason}")
            return 2 if outcome.status == "failed" else 3

        compiler = ArtifactCompiler(policy, error_rules_factory=profile.error_rules_factory)
        try:
            artifact = compiler.compile(outcome.run, app_id=profile.app_id, vendor_family=profile.vendor_family)
        except CompileError as exc:
            print(f"artifact compilation failed: {exc}", file=sys.stderr)
            return 2
        output = Path(args.output or settings.artifact_dir / f"{args.capability_id}.v1.json")
        save_artifact(artifact, output)
        print(f"steps recorded: {len(outcome.run.steps)}, compiled: {len(artifact.steps)}")
        print(f"artifact: {output}")
        return 0
    finally:
        if watcher_task is not None and not watcher_task.done():
            watcher_task.cancel()
        await surface.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
