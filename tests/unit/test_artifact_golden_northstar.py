"""Regression fence: Phase-2 schema work must not change what Northstar compiles.

Every Phase-2 core change (extract modes, internal captures, the `json` value
type, artifact-scoped escalation) touches the artifact schema. This test pins
the compiled Northstar artifact byte-for-byte, and pins the two committed
Phase-1 artifacts, so any drift is caught the moment it happens rather than at
submission time.

To re-bless intentionally: delete the golden file and re-run.
"""

import json
from pathlib import Path

from tests.unit.test_compiler import compiler, make_run
from ui_capabilities.discovery.compiler import load_artifact

GOLDEN = Path(__file__).parent.parent / "fixtures" / "golden" / "northstar_balance.json"
COMMITTED = [
    Path("artifacts/member.get_savings_balance.v1.json"),
    Path("evidence/example_capability.json"),
]


def _canonical(artifact) -> str:
    return json.dumps(json.loads(artifact.model_dump_json()), indent=2, sort_keys=True) + "\n"


def test_compiled_northstar_artifact_is_unchanged():
    produced = _canonical(compiler().compile(make_run()))
    if not GOLDEN.exists():  # first run blesses the snapshot
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(produced)
    assert produced == GOLDEN.read_text(), (
        "the compiled Northstar artifact changed; Phase-2 schema work must not alter Phase-1 output"
    )


def test_new_schema_fields_do_not_appear_in_northstar_output():
    """Additive fields must stay at their defaults for a target that never uses them."""
    artifact = compiler().compile(make_run())
    assert artifact.policy.escalate_on_codes == []
    for step in artifact.steps:
        assert step.internal is False
        if step.action != "extract":
            assert step.extract_mode is None
    for spec in artifact.contract.inputs:
        assert spec.credential is False, "Northstar declares no credential inputs"


def test_committed_phase_one_artifacts_still_load_and_validate():
    for path in COMMITTED:
        assert path.exists(), f"missing committed artifact {path}"
        artifact = load_artifact(path)
        assert artifact.capability_id == "member.get_savings_balance"
        assert artifact.policy.escalate_on_codes == []
        assert all(s.internal is False for s in artifact.steps)
