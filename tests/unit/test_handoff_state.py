import asyncio

import pytest

from tests.fixtures.fakes import FakeSurface
from ui_capabilities.handoff.manager import HandoffError, HandoffManager
from ui_capabilities.handoff.store import InterventionStore
from ui_capabilities.models.intervention import ControlOwner, RunMode
from ui_capabilities.observability.logger import RunLogger
from ui_capabilities.policy.redaction import Redactor


@pytest.fixture
def manager(tmp_path):
    surface = FakeSurface(tmp_path)
    redactor = Redactor()
    logger = RunLogger(tmp_path / "run.jsonl", redactor, "run-1")
    return HandoffManager(
        store=InterventionStore(dump_path=tmp_path / "interventions.json"),
        surface=surface,
        logger=logger,
        redactor=redactor,
    )


async def _request(manager):
    return await manager.request_intervention(
        run_id="run-1",
        mode=RunMode.REPLAY,
        capability_id="member.open_sub_account",
        goal_summary="open sub account",
        step_id="s7_click",
        reason_code="HUMAN_APPROVAL_REQUIRED",
        reason_message="irreversible step",
    )


async def test_full_transition_cycle(manager):
    assert manager.control_owner == ControlOwner.AUTOMATION
    intervention = await _request(manager)
    assert manager.control_owner == ControlOwner.PAUSED
    assert intervention.status == "open"

    await manager.take_control(intervention.intervention_id, "op-1")
    assert manager.control_owner == ControlOwner.HUMAN
    assert manager.surface.human_capture is True

    await manager.resume(intervention.intervention_id)
    assert manager.control_owner == ControlOwner.PAUSED
    assert manager.surface.human_capture is False

    manager.confirm_automation_resumed(intervention.intervention_id)
    assert manager.control_owner == ControlOwner.AUTOMATION
    assert manager.store.get(intervention.intervention_id).status == "resolved"


async def test_wait_unblocks_on_resume(manager):
    intervention = await _request(manager)

    async def operator():
        await manager.take_control(intervention.intervention_id, "op-1")
        await manager.resume(intervention.intervention_id)

    task = asyncio.create_task(operator())
    result = await asyncio.wait_for(manager.wait(intervention.intervention_id), timeout=2)
    await task
    assert result == "resumed"


async def test_invalid_transitions_rejected(manager):
    intervention = await _request(manager)
    # resume before take
    with pytest.raises(HandoffError):
        await manager.resume(intervention.intervention_id)
    # double intervention while paused
    with pytest.raises(HandoffError):
        await _request(manager)
    await manager.take_control(intervention.intervention_id, "op-1")
    # double take
    with pytest.raises(HandoffError):
        await manager.take_control(intervention.intervention_id, "op-2")


async def test_abort_is_terminal(manager):
    intervention = await _request(manager)
    await manager.abort(intervention.intervention_id)
    assert manager.store.get(intervention.intervention_id).status == "aborted"
    assert await manager.wait(intervention.intervention_id) == "aborted"
    with pytest.raises(HandoffError):
        await manager.take_control(intervention.intervention_id, "op-1")
    with pytest.raises(HandoffError):
        await manager.abort(intervention.intervention_id)


async def test_human_event_values_never_survive(manager):
    intervention = await _request(manager)
    await manager.take_control(intervention.intervention_id, "op-1")
    manager.surface.human_events = [
        {"event": "click", "tag": "button", "text": "Confirm Open Account", "timestamp": "t"},
        {"event": "change", "tag": "input", "name": "nickname", "value_changed": True, "value": "raw-typed-value"},
        {"event": "navigation", "url": "/members/M-10001/subaccounts/confirmed", "timestamp": "t"},
        "garbage",
    ]
    await manager.resume(intervention.intervention_id)
    stored = manager.store.get(intervention.intervention_id)
    assert len(stored.human_events) == 3
    change = next(e for e in stored.human_events if e.event == "change")
    assert change.value == "[REDACTED]"
    assert change.value_changed is True
    dump = (manager.store._dump_path).read_text()
    assert "raw-typed-value" not in dump
