#!/usr/bin/env python3
"""Genuine MERIDIAN replay with a scripted stand-in for the human operator.

Mirrors `uicap replay` (`ui_capabilities.cli._replay`) exactly — same
settings, policy, surface, evidence, logger, and `ReplayEngine` — but adds a
concurrent watcher that plays the human-operator role for a risky/irreversible
click gate, exactly as `tests/integration/test_handoff.py` already does for
automated verification and `scripts/meridian_discover.py` does for discovery.

Only ever approves `reason_code == "HUMAN_APPROVAL_REQUIRED"` (the ordinary
policy gate on a declared risky/irreversible step, `ReplayEngine._escalate_step`'s
default code). Any other reason — e.g. a detected
condition an artifact declares as `escalate_on_codes` (SUPERVISOR_REQUIRED) —
is left for the caller to handle explicitly via `--on-detected-code`, which
runs a small sequence of raw Playwright actions against the SAME live page
(sign off, sign on as a different operator, re-navigate) before resuming; this
is how the teller -> supervisor escalation path is exercised end to end
without a real human physically present.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ui_capabilities.config import Settings  # noqa: E402
from ui_capabilities.discovery.compiler import load_artifact  # noqa: E402
from ui_capabilities.handoff.manager import HandoffManager  # noqa: E402
from ui_capabilities.handoff.store import InterventionStore  # noqa: E402
from ui_capabilities.observability.evidence import EvidenceManager  # noqa: E402
from ui_capabilities.observability.logger import RunLogger  # noqa: E402
from ui_capabilities.policy.engine import PolicyEngine  # noqa: E402
from ui_capabilities.policy.redaction import Redactor  # noqa: E402
from ui_capabilities.replay.engine import ReplayEngine  # noqa: E402
from ui_capabilities.surfaces.playwright_web import PlaywrightWebSurface  # noqa: E402
from ui_capabilities.targets import get_profile  # noqa: E402
from ui_capabilities.targets.registry import profile_for_app_id  # noqa: E402


def _parse_inputs(pairs: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in pairs:
        name, _, value = pair.partition("=")
        out[name.strip()] = value.strip()
    return out


async def _auto_operator(
    handoff: HandoffManager,
    store: InterventionStore,
    surface: PlaywrightWebSurface,
    caption: str | None,
    supervisor_creds: dict[str, str] | None,
    hold_reentry: dict[str, str] | None,
    seen: set[str],
) -> None:
    """Approve every intervention as it appears, until cancelled by the caller
    once replay finishes (a run may need more than one — e.g. a
    SUPERVISOR_REQUIRED detected-state escalation followed by the ordinary
    risky-click gate on the same run).

    reason_code == "HUMAN_APPROVAL_REQUIRED": click the named control (the
    ordinary policy gate on a declared risky/irreversible step).

    Any other reason_code (a detected condition the artifact routes to a
    human, e.g. SUPERVISOR_REQUIRED): if supervisor_creds is given, sign off,
    sign on as the supervisor, re-enter the SAME in-flight request (per
    hold_reentry) up to the point the interrupted step expects, then resume —
    the engine re-validates that step's own checkpoint, so this only ever
    proceeds if the re-entry actually reached it.
    """
    while True:
        for item in store.all():
            if item.intervention_id in seen or item.status != "open":
                continue
            seen.add(item.intervention_id)
            print(f"\n[auto-operator] intervention {item.intervention_id}: {item.reason_code} — {item.reason_message}")
            if item.reason_code == "HUMAN_APPROVAL_REQUIRED":
                if not caption:
                    print("[auto-operator] no --approve-caption given for a risky-click gate; aborting")
                    await handoff.abort(item.intervention_id, note="no caption configured")
                    return
                print(f"[auto-operator] taking control and clicking {caption!r} on the live page")
                await handoff.take_control(item.intervention_id, operator_id="scripted-operator")
                await surface.page.get_by_role("button", name=caption).click()
                await surface.page.wait_for_load_state("load")
                print("[auto-operator] resuming automation")
                await handoff.resume(item.intervention_id, note=f"scripted operator approved {caption!r}")
                continue
            if supervisor_creds and hold_reentry:
                # MERIDIAN renders no id/aria-label/<label> at all (the same
                # finding the artifacts' own `stable_attribute name=` locators
                # are built on) — role+accessible-name lookups resolve to
                # nothing on its textboxes/selects, unlike its submit buttons
                # (whose accessible name IS their `value` caption). Address
                # every non-button control the same way the compiled steps
                # do: by its `name` attribute.
                print("[auto-operator] detected-state escalation: signing off and back on as supervisor")
                await handoff.take_control(item.intervention_id, operator_id="scripted-supervisor")
                page = surface.page
                origin = hold_reentry["origin"]
                await page.get_by_role("link", name="Sign Off").click()
                await page.wait_for_load_state("load")
                await page.locator('input[name="operator"]').fill(supervisor_creds["operator_id"])
                await page.locator('input[name="password"]').fill(supervisor_creds["password"])
                await page.locator('select[name="branch"]').select_option(supervisor_creds["branch"])
                await page.get_by_role("button", name="Sign On").click()
                await page.wait_for_load_state("load")
                print("[auto-operator] re-entering the same in-flight hold request as supervisor")
                await page.goto(f"{origin}/members/{hold_reentry['member_number']}/hold", wait_until="load")
                await page.locator('select[name="share"]').select_option(hold_reentry["share"])
                await page.locator('select[name="reason"]').select_option(hold_reentry["reason_code"])
                if hold_reentry.get("notes"):
                    await page.locator('input[name="notes"]').fill(hold_reentry["notes"])
                await page.get_by_role("button", name="Continue").click()
                await page.wait_for_load_state("load")
                print("[auto-operator] resuming automation for the engine to re-validate the interrupted step")
                await handoff.resume(item.intervention_id, note="supervisor re-entered the hold request")
                continue
            print(f"[auto-operator] reason_code {item.reason_code!r} has no configured handler; aborting")
            await handoff.abort(item.intervention_id, note=f"no handler for reason_code={item.reason_code!r}")
            return
        await asyncio.sleep(0.2)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--app", default="meridian")
    parser.add_argument("--input", action="append", default=[], metavar="NAME=VALUE")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--approve-caption", default=None, help="accessible name of the risky/irreversible control to approve")
    parser.add_argument("--supervisor-operator-id", default=None)
    parser.add_argument("--supervisor-password", default=None)
    parser.add_argument("--supervisor-branch", default="MAIN-001")
    parser.add_argument("--hold-member-number", default=None, help="for re-entering an in-flight hold request as supervisor")
    parser.add_argument("--hold-share", default=None)
    parser.add_argument("--hold-reason-code", default=None)
    parser.add_argument("--hold-notes", default=None)
    args = parser.parse_args()

    settings = Settings.load()
    artifact = load_artifact(args.artifact)
    inputs = _parse_inputs(args.input)
    run_id = f"rep-{uuid.uuid4().hex[:10]}"
    evidence = EvidenceManager(settings.evidence_dir, run_id)
    profile = profile_for_app_id(artifact.target.app_id) or get_profile(args.app)
    redactor = Redactor(text_patterns=profile.redaction_text_patterns)
    logger = RunLogger(evidence.log_path, redactor, run_id)
    policy = PolicyEngine(profile.policy(artifact.target.entry_point))

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

    supervisor_creds = None
    if args.supervisor_operator_id and args.supervisor_password:
        supervisor_creds = {
            "operator_id": args.supervisor_operator_id,
            "password": args.supervisor_password,
            "branch": args.supervisor_branch,
        }

    hold_reentry = None
    if args.hold_member_number and args.hold_share and args.hold_reason_code:
        from urllib.parse import urlparse

        origin = urlparse(artifact.target.entry_point)
        hold_reentry = {
            "origin": f"{origin.scheme}://{origin.netloc}",
            "member_number": args.hold_member_number,
            "share": args.hold_share,
            "reason_code": args.hold_reason_code,
            "notes": args.hold_notes or "",
        }

    watcher_task = asyncio.create_task(
        _auto_operator(handoff, store, surface, args.approve_caption, supervisor_creds, hold_reentry, set())
    )
    try:
        engine = ReplayEngine(surface=surface, global_policy=policy, settings=settings, logger=logger, evidence=evidence, redactor=redactor, handoff=handoff)
        result = await engine.replay(artifact, inputs)
        import json

        print("\n=== replay result ===")
        print(json.dumps(result.model_dump(), indent=2, default=str))
        print(f"evidence: {evidence.run_dir}")
        return {"success": 0, "business_outcome": 0, "failure": 2, "escalated": 3}.get(result.status, 2)
    finally:
        if not watcher_task.done():
            watcher_task.cancel()
        await surface.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
