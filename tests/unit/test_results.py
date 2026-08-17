import json

from pydantic import TypeAdapter

from ui_capabilities.models.results import (
    BusinessOutcomeResult,
    EscalatedResult,
    FailureResult,
    RecoveryRecord,
    RunResult,
    SuccessResult,
)
from ui_capabilities.observability.logger import RunLogger
from ui_capabilities.policy.redaction import REDACTED, Redactor

adapter = TypeAdapter(RunResult)


def test_result_contract_discriminates_by_status():
    success = SuccessResult(
        run_id="r1",
        capability_id="member.get_savings_balance",
        capability_version="1.0.0",
        outputs={"savings_balance": 2540.75},
        recoveries=[RecoveryRecord(step_id="s4_click", code="KNOWN_INTERSTITIAL", attempts=1, outcome="recovered")],
    )
    parsed = adapter.validate_python(json.loads(success.model_dump_json()))
    assert isinstance(parsed, SuccessResult)

    outcome = BusinessOutcomeResult(
        run_id="r2", capability_id="c", capability_version="1.0.0",
        code="MEMBER_NOT_FOUND", message="No member matched the supplied identifier.", step_id="s3_click",
    )
    assert isinstance(adapter.validate_python(outcome.model_dump()), BusinessOutcomeResult)

    failure = FailureResult(
        run_id="r3", code="TARGET_NOT_FOUND", step_id="s4_click",
        expected="Accounts link resolvable", observed="no strategy matched", evidence=["x.png"],
    )
    assert isinstance(adapter.validate_python(failure.model_dump()), FailureResult)

    escalated = EscalatedResult(
        run_id="r4", code="HUMAN_APPROVAL_REQUIRED", intervention_id="int-1",
        step_id="s7_click", message="irreversible confirmation requires a human",
    )
    assert isinstance(adapter.validate_python(escalated.model_dump()), EscalatedResult)


def test_sensitive_outputs_returned_to_caller_but_redacted_in_logs(tmp_path):
    redactor = Redactor()
    redactor.register_sensitive_value("2540.75")
    result = SuccessResult(run_id="r1", capability_id="c", capability_version="1.0.0", outputs={"savings_balance": 2540.75})
    # caller sees the real value
    assert result.outputs["savings_balance"] == 2540.75
    # persisted log does not
    logger = RunLogger(tmp_path / "run.jsonl", redactor, "r1")
    logger.event("replay_result", outputs={k: str(v) for k, v in result.outputs.items()})
    raw = (tmp_path / "run.jsonl").read_text()
    assert "2540.75" not in raw
    assert REDACTED in raw
