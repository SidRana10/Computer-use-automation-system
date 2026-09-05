"""Durable Playwright traces are a target decision, not a global default.

Audited during P1: a MERIDIAN `trace.zip` contained the sign-on POST body
verbatim (`operator=...&password=...`), every `fill` action's parameter value,
unmasked frame screenshots, and raw DOM resources. Screenshot masking and DOM
redaction operate on what the surface writes, not on Playwright's recorder, so
there is no sanitisation path into a trace. MERIDIAN therefore records no
durable trace; Northstar, whose data is synthetic and local, is unchanged.
"""

from ui_capabilities.targets import get_profile


def test_meridian_disables_durable_traces():
    assert get_profile("meridian").durable_traces is False


def test_northstar_keeps_phase_one_tracing():
    assert get_profile("northstar").durable_traces is True


async def test_surface_start_trace_is_a_noop_when_disabled(tmp_path):
    """No context is touched, so no trace file can ever be produced."""
    from ui_capabilities.config import Settings
    from ui_capabilities.observability.evidence import EvidenceManager
    from ui_capabilities.surfaces.playwright_web import PlaywrightWebSurface

    evidence = EvidenceManager(tmp_path, "trace-test")
    surface = PlaywrightWebSurface(Settings(), evidence, headless=True, enable_tracing=False)
    await surface.start_trace()          # must not raise despite no browser
    assert surface._tracing is False
    assert await surface.stop_trace() is None
    assert not evidence.trace_path.exists()


def test_the_evidence_a_traceless_target_still_produces_is_declared():
    """Losing traces must not silently lose the rest of the evidence set."""
    profile = get_profile("meridian")
    assert profile.screenshot_mask_selectors, "masked screenshots remain"
    assert profile.redaction_text_patterns, "redacted logs and DOM snapshots remain"
