"""P6: CapabilityService is the one place invocation rules live —
credential injection, contract validation before any runner call, and
rejection of caller-supplied credential/policy-override fields.

All of this is tested against a `FakeRunner` (see `_api_test_support.py`):
none of it needs, or should need, a live browser or a live MERIDIAN target.
"""

from __future__ import annotations

import pytest

from ui_capabilities.api.catalog import CapabilityNotFoundError
from ui_capabilities.api.service import InvalidArgumentsError
from ui_capabilities.models.errors import FailureCode
from ui_capabilities.models.results import BusinessOutcomeResult, FailureResult, SuccessResult

from _api_test_support import make_service


def _success(artifact, inputs):
    return SuccessResult(
        run_id="api-test-run-1",
        capability_id=artifact.capability_id,
        capability_version=artifact.capability_version,
        outputs={"shares": [{"share": "100234-S0001-12", "balance": "1,234.56"}]},
    )


async def test_invoke_rejects_unknown_capability_before_touching_runner(tmp_path):
    service, runner = make_service(tmp_path, _success)
    with pytest.raises(CapabilityNotFoundError):
        await service.invoke("meridian.not_a_real_capability", {"member_number": "100234"})
    assert runner.calls == []


@pytest.mark.parametrize("forbidden_field, value", [("operator_id", "teller1"), ("password", "hunter2"), ("branch", "MAIN-001"), ("human_approved", True)])
async def test_invoke_rejects_server_supplied_or_policy_override_fields(tmp_path, forbidden_field, value):
    service, runner = make_service(tmp_path, _success)
    with pytest.raises(InvalidArgumentsError):
        await service.invoke("meridian.get_member_balances", {"member_number": "100234", forbidden_field: value})
    assert runner.calls == [], "a rejected request must never reach the runner"


async def test_invoke_rejects_missing_required_input_before_touching_runner(tmp_path):
    service, runner = make_service(tmp_path, _success)
    result = await service.invoke("meridian.get_member_balances", {})
    assert isinstance(result, FailureResult)
    assert result.code == FailureCode.INVOCATION_INVALID
    assert runner.calls == [], "invalid typed args must fail before any browser/runner action"


async def test_invoke_injects_operator_credentials_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")
    monkeypatch.setenv("MERIDIAN_BRANCH", "MAIN-001")
    service, runner = make_service(tmp_path, _success)

    result = await service.invoke("meridian.get_member_balances", {"member_number": "100234"})

    assert isinstance(result, SuccessResult)
    assert len(runner.calls) == 1
    _, bound_inputs = runner.calls[0]
    assert bound_inputs["operator_id"] == "teller1"
    assert bound_inputs["password"] == "s3cret"
    assert bound_inputs["branch"] == "MAIN-001"
    assert bound_inputs["member_number"] == "100234"


async def test_successful_invocation_is_recorded_and_retrievable(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")
    service, _ = make_service(tmp_path, _success)

    result = await service.invoke("meridian.get_member_balances", {"member_number": "100234"})

    detail = service.get_run(result.run_id)
    assert detail.status == "success"
    assert detail.capability_id == "meridian.get_member_balances"
    assert detail.result.outputs == {"shares": [{"share": "100234-S0001-12", "balance": "1,234.56"}]}
    # the sensitive business input is redacted in durable run history
    assert detail.inputs["member_number"] == "[REDACTED]"
    # credentials were never even given to the run store to begin with
    assert "operator_id" not in detail.inputs
    assert "password" not in detail.inputs

    summaries = service.list_runs()
    assert any(s.run_id == result.run_id for s in summaries)


async def test_non_sensitive_input_is_shown_unredacted_in_run_history(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")

    def _member_inquiry_success(artifact, inputs):
        return SuccessResult(
            run_id="api-test-run-2",
            capability_id=artifact.capability_id,
            capability_version=artifact.capability_version,
            outputs={"member_results": [], "member_results_table": []},
        )

    service, _ = make_service(tmp_path, _member_inquiry_success)
    result = await service.invoke(
        "meridian.member_inquiry", {"search_mode": "number", "search_value": "100234"}
    )
    detail = service.get_run(result.run_id)
    # search_mode is not declared sensitive; search_value is.
    assert detail.inputs["search_mode"] == "number"
    assert detail.inputs["search_value"] == "[REDACTED]"


async def test_business_outcome_and_failure_results_pass_through_unmodified(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")

    def _policy_blocked(artifact, inputs):
        return FailureResult(
            run_id="api-test-run-3",
            capability_id=artifact.capability_id,
            capability_version=artifact.capability_version,
            code=FailureCode.POLICY_BLOCKED,
            observed="route not in allowed route patterns",
        )

    service, _ = make_service(tmp_path, _policy_blocked)
    result = await service.invoke("meridian.get_member_balances", {"member_number": "100234"})
    assert isinstance(result, FailureResult)
    assert result.code == FailureCode.POLICY_BLOCKED

    def _business_outcome(artifact, inputs):
        return BusinessOutcomeResult(
            run_id="api-test-run-4",
            capability_id=artifact.capability_id,
            capability_version=artifact.capability_version,
            code="MEMBER_NOT_FOUND",
            message="No member matches that number.",
        )

    service2, _ = make_service(tmp_path, _business_outcome)
    result2 = await service2.invoke("meridian.get_member_balances", {"member_number": "999999"})
    assert isinstance(result2, BusinessOutcomeResult)
    assert result2.code == "MEMBER_NOT_FOUND"
