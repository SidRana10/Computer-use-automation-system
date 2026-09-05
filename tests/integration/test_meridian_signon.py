"""Live MERIDIAN sign-on through the ordinary deterministic replay path.

Opt in with MERIDIAN_LIVE=1 (plus credentials); skipped otherwise so the default
suite stays hermetic and offline. Assertions are structural: the sample
application is shared and mutable, so exact data is never asserted.
"""

import os
import uuid

import pytest

from ui_capabilities.config import Settings
from ui_capabilities.discovery.compiler import load_artifact
from ui_capabilities.observability.evidence import EvidenceManager
from ui_capabilities.observability.logger import RunLogger
from ui_capabilities.policy.engine import PolicyEngine
from ui_capabilities.policy.redaction import Redactor
from ui_capabilities.replay.engine import ReplayEngine
from ui_capabilities.surfaces.playwright_web import PlaywrightWebSurface
from ui_capabilities.targets import get_profile

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(os.environ.get("MERIDIAN_LIVE") != "1", reason="set MERIDIAN_LIVE=1 to run live MERIDIAN tests"),
]

ARTIFACT = "artifacts/meridian/meridian.sign_on.v1.json"


async def _run(tmp_path, inputs: dict[str, str]):
    profile = get_profile("meridian")
    artifact = load_artifact(ARTIFACT)
    settings = Settings(playwright_headless=True, evidence_dir=tmp_path / "evidence")
    evidence = EvidenceManager(settings.evidence_dir, f"live-{uuid.uuid4().hex[:8]}")
    redactor = Redactor(text_patterns=profile.redaction_text_patterns)
    surface = PlaywrightWebSurface(
        settings,
        evidence,
        headless=True,
        heading_selector=profile.heading_selector,
        mask_selectors=profile.screenshot_mask_selectors,
        redactor=redactor,
        enable_tracing=profile.durable_traces,
    )
    engine = ReplayEngine(
        surface=surface,
        global_policy=PolicyEngine(profile.policy(artifact.target.entry_point)),
        settings=settings,
        logger=RunLogger(evidence.log_path, redactor, evidence.run_id),
        evidence=evidence,
        redactor=redactor,
    )
    try:
        return await engine.replay(artifact, inputs), evidence
    finally:
        await surface.close()


def _creds(role: str) -> dict[str, str]:
    prefix = "MERIDIAN_TELLER" if role == "teller" else "MERIDIAN_SUPERVISOR"
    return {
        "operator_id": os.environ.get(f"{prefix}_ID", ""),
        "password": os.environ.get(f"{prefix}_PASSWORD", ""),
        "branch": os.environ.get("MERIDIAN_BRANCH", "MAIN-001"),
    }


@pytest.mark.parametrize("role", ["teller", "supervisor"])
async def test_signon_succeeds_for_both_roles(tmp_path, role):
    result, _ = await _run(tmp_path, _creds(role))
    assert result.status == "success", f"{role}: {result.model_dump()}"
    assert result.capability_id == "meridian.sign_on"


async def test_bad_password_is_a_business_outcome_not_a_crash(tmp_path):
    creds = _creds("teller") | {"password": "definitely-not-the-password"}
    result, _ = await _run(tmp_path, creds)
    assert result.status == "business_outcome"
    assert result.code == "BAD_LOGIN"


async def test_no_playwright_trace_is_written_for_meridian(tmp_path):
    """A trace is a raw recording no redactor can reach inside.

    Audited during P1: a MERIDIAN trace.zip held the sign-on POST body verbatim
    (`operator=...&password=...`), every fill parameter, unmasked frame images
    and raw DOM. There is no sanitisation path into it, so none is written.
    """
    _, evidence = await _run(tmp_path, _creds("teller"))
    assert not evidence.trace_path.exists()
    assert not list(evidence.run_dir.rglob("*.zip"))
    # the evidence that replaces it must still be there
    assert evidence.log_path.exists()
    assert list(evidence.run_dir.rglob("*.png"))


async def test_durable_evidence_carries_no_session_identifier_or_token(tmp_path):
    _, evidence = await _run(tmp_path, _creds("teller"))
    for path in evidence.run_dir.rglob("*"):
        if not path.is_file() or path.suffix not in {".html", ".jsonl"}:
            continue
        body = path.read_text(errors="ignore")
        assert "SID " not in body or "[REDACTED]" in body
        assert 'name="_token" value="' not in body.replace('value="[REDACTED]"', "")


async def test_masked_regions_are_removed_from_durable_evidence(tmp_path):
    """Surface-level check of the profile-driven masking, on a page that
    actually renders member data.

    This also pins the ordering bug found during P1: region scrubbing must run
    before value/pattern redaction. With the member number registered as a
    runtime value, redacting it first turns "Member 100234 - Lovelace, Ada" into
    "Member [REDACTED] - Lovelace, Ada", the region text no longer matches the
    markup, and the member name survives into the snapshot.
    """
    profile = get_profile("meridian")
    settings = Settings(playwright_headless=True, evidence_dir=tmp_path / "evidence")
    evidence = EvidenceManager(settings.evidence_dir, f"mask-{uuid.uuid4().hex[:8]}")
    redactor = Redactor(text_patterns=profile.redaction_text_patterns)
    redactor.register_sensitive_value("100234")  # as a bound member_number input would be
    surface = PlaywrightWebSurface(
        settings,
        evidence,
        headless=True,
        heading_selector=profile.heading_selector,
        mask_selectors=profile.screenshot_mask_selectors,
        redactor=redactor,
        enable_tracing=profile.durable_traces,
    )
    creds = _creds("teller")
    try:
        await surface.start(f"{profile.default_entry_point}/signon")
        page = surface.page
        await page.fill('input[name="operator"]', creds["operator_id"])
        await page.fill('input[name="password"]', creds["password"])
        await page.get_by_role("button", name="Sign On").click()
        await page.wait_for_load_state("load")
        await page.goto(f"{profile.default_entry_point}/members/100234", wait_until="load")

        observation = await surface.observe(label="member_record")
        assert observation.heading == "MEMBER RECORD", "profile heading selector must read <h1> here"

        snapshot = await surface.capture_dom_snapshot("member_record")
        body = snapshot.read_text()
        for leaked in ("Lovelace", "100234", "replay-verify@example.com", "Verify Lane", "SID ", "OPR TELLER"):
            assert leaked not in body, f"{leaked!r} survived into a durable DOM snapshot"
        assert "MEMBER RECORD" in body, "structure must survive so the evidence stays useful"

        shot = await surface.capture_screenshot("member_record")
        assert shot.exists() and shot.stat().st_size > 0
    finally:
        await surface.close()
