"""Same-session human handoff: replay pauses at the irreversible confirm, a
'human' (this test) operates the SAME live Playwright page, automation
validates and completes."""

import asyncio

import pytest

from tests.fixtures.factories import make_subaccount_artifact
from ui_capabilities.handoff.manager import HandoffManager
from ui_capabilities.handoff.store import InterventionStore
from ui_capabilities.models.intervention import ControlOwner

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("demo_state", "cleanup_surface")]


@pytest.fixture
def handoff(harness):
    store = InterventionStore(dump_path=harness.evidence.run_dir / "interventions.json")
    return HandoffManager(
        store=store,
        surface=harness.surface,
        logger=harness.logger,
        redactor=harness.redactor,
        operator_base_url="http://127.0.0.1:0",
    )


async def _wait_for_intervention(store: InterventionStore, timeout: float = 15.0):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        items = store.all()
        if items:
            return items[0]
        await asyncio.sleep(0.1)
    raise AssertionError("no intervention was raised")


async def test_irreversible_step_routes_to_human_and_resumes_same_session(demo_server, harness, replay_engine, handoff):
    artifact = make_subaccount_artifact(demo_server)
    engine = replay_engine(handoff=handoff)

    replay_task = asyncio.create_task(
        engine.replay(artifact, {"member_id": "M-10001", "account_type": "Holiday Savings"})
    )

    intervention = await _wait_for_intervention(handoff.store)
    assert intervention.step_id == "s7_click"
    assert intervention.reason_code == "HUMAN_APPROVAL_REQUIRED"
    assert handoff.control_owner == ControlOwner.PAUSED
    assert intervention.screenshot_path  # context for the operator
    # automation is paused on the review page of the SAME live session
    page = harness.surface.page
    assert "Review New Sub-Account" in await page.inner_text("body")

    # operator takes control and the human confirms in the same browser
    await handoff.take_control(intervention.intervention_id, "op-test")
    assert handoff.control_owner == ControlOwner.HUMAN
    await page.get_by_role("button", name="Confirm Open Account").click()
    await page.wait_for_load_state("load")
    assert "Sub-account opened successfully." in await page.inner_text("body")

    # operator hands control back; automation validates the checkpoint and finishes
    await handoff.resume(intervention.intervention_id, note="confirmed manually")
    result = await asyncio.wait_for(replay_task, timeout=30)

    assert result.status == "success", getattr(result, "message", result)
    assert result.outputs["confirmation_number"].startswith("SUB-")
    assert result.human_completions and result.human_completions[0].step_id == "s7_click"
    assert handoff.control_owner == ControlOwner.AUTOMATION

    # redacted human evidence was captured (click on the confirm button)
    stored = handoff.store.get(intervention.intervention_id)
    assert stored.status == "resolved"
    assert any(e.event == "click" and (e.text or "").startswith("Confirm") for e in stored.human_events)
    assert all(e.value in (None, "[REDACTED]") for e in stored.human_events)
    assert stored.after_screenshot


async def test_operator_abort_returns_escalated_result(demo_server, harness, replay_engine, handoff):
    artifact = make_subaccount_artifact(demo_server)
    engine = replay_engine(handoff=handoff)
    replay_task = asyncio.create_task(
        engine.replay(artifact, {"member_id": "M-10001", "account_type": "Vacation Club"})
    )
    intervention = await _wait_for_intervention(handoff.store)
    await handoff.abort(intervention.intervention_id, note="operator declined")
    result = await asyncio.wait_for(replay_task, timeout=30)
    assert result.status == "escalated"
    assert result.resolution == "aborted"
    assert result.intervention_id == intervention.intervention_id
    assert result.step_id == "s7_click"


async def test_escalation_without_handoff_channel_returns_escalated(demo_server, replay_engine):
    artifact = make_subaccount_artifact(demo_server)
    result = await replay_engine(handoff=None).replay(artifact, {"member_id": "M-10001", "account_type": "Holiday Savings"})
    assert result.status == "escalated"
    assert result.code == "HUMAN_APPROVAL_REQUIRED"
    assert result.step_id == "s7_click"


async def test_permission_denied_member_is_business_outcome(demo_server, replay_engine):
    artifact = make_subaccount_artifact(demo_server)
    result = await replay_engine(handoff=None).replay(artifact, {"member_id": "M-10002", "account_type": "Holiday Savings"})
    assert result.status == "business_outcome"
    assert result.code == "PERMISSION_DENIED"
    assert result.step_id == "s4_click"
