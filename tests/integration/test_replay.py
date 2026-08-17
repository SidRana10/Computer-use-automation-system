"""End-to-end deterministic replay against the live demo app (headless).
No LLM anywhere in these tests."""

import pytest

from tests.fixtures.factories import make_balance_artifact

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("demo_state", "cleanup_surface")]


async def test_replay_success_with_different_member(demo_server, replay_engine):
    """The artifact was 'recorded' with M-10001; replaying M-10003 proves
    parameterization."""
    artifact = make_balance_artifact(demo_server)
    result = await replay_engine().replay(artifact, {"member_id": "M-10003"})
    assert result.status == "success", getattr(result, "observed", result)
    assert result.outputs["savings_balance"] == pytest.approx(87.12)
    assert result.recoveries == []


async def test_replay_unknown_member_is_business_outcome_not_crash(demo_server, replay_engine):
    artifact = make_balance_artifact(demo_server)
    result = await replay_engine().replay(artifact, {"member_id": "M-40400"})
    assert result.status == "business_outcome"
    assert result.code == "MEMBER_NOT_FOUND"
    assert result.step_id == "s3_click"
    assert result.message


async def test_replay_invalid_input_fails_before_browser(demo_server, replay_engine, harness):
    artifact = make_balance_artifact(demo_server)
    result = await replay_engine().replay(artifact, {"member_id": "BAD"})
    assert result.status == "failure"
    assert result.code == "INVOCATION_INVALID"
    # the browser was never started
    assert harness.surface._page is None


async def test_replay_malformed_id_reaching_ui_is_validation_outcome(demo_server, replay_engine):
    artifact = make_balance_artifact(demo_server, member_id_pattern=None)
    result = await replay_engine().replay(artifact, {"member_id": "BAD"})
    assert result.status == "business_outcome"
    assert result.code == "VALIDATION_REJECTED"


async def test_replay_recovers_from_known_interstitial(demo_server, demo_state, replay_engine):
    demo_state.interstitial_pending = True
    artifact = make_balance_artifact(demo_server)
    result = await replay_engine().replay(artifact, {"member_id": "M-10001"})
    assert result.status == "success", getattr(result, "observed", result)
    assert result.outputs["savings_balance"] == pytest.approx(2540.75)
    assert any(r.code == "KNOWN_INTERSTITIAL" and r.outcome == "recovered" for r in result.recoveries)


async def test_replay_recovers_from_transient_load(demo_server, demo_state, replay_engine):
    demo_state.slow_accounts_pending = True
    artifact = make_balance_artifact(demo_server)
    result = await replay_engine().replay(artifact, {"member_id": "M-10001"})
    assert result.status == "success", getattr(result, "observed", result)
    assert any(r.code == "TRANSIENT_LOAD" and r.outcome == "recovered" for r in result.recoveries)


async def test_replay_hard_failure_on_missing_control(demo_server, demo_state, replay_engine, harness):
    demo_state.failure_mode = "missing_accounts_control"
    artifact = make_balance_artifact(demo_server)
    result = await replay_engine().replay(artifact, {"member_id": "M-10001"})
    assert result.status == "failure"
    assert result.code in ("TARGET_NOT_FOUND", "AMBIGUOUS_TARGET")
    assert result.step_id == "s4_click"
    assert "Accounts" in result.expected
    assert result.observed
    # richer failure evidence: a screenshot was captured
    screenshots = [e for e in result.evidence if e.endswith(".png")]
    assert screenshots and any("failure" in s for s in screenshots)
    import json
    from pathlib import Path

    log_lines = [json.loads(line) for line in Path(harness.evidence.log_path).read_text().splitlines()]
    assert any(entry["event"] == "hard_failure" for entry in log_lines)


async def test_replay_session_expired_is_declared_hard_failure(demo_server, demo_state, replay_engine):
    demo_state.session_expired = True
    artifact = make_balance_artifact(demo_server)
    result = await replay_engine().replay(artifact, {"member_id": "M-10001"})
    assert result.status == "failure"
    assert result.code == "SESSION_EXPIRED"


async def test_replay_logs_are_redacted(demo_server, replay_engine, harness):
    artifact = make_balance_artifact(demo_server)
    result = await replay_engine().replay(artifact, {"member_id": "M-10003"})
    assert result.status == "success"
    raw_log = harness.evidence.log_path.read_text()
    assert "M-10003" not in raw_log
    assert "87.12" not in raw_log
