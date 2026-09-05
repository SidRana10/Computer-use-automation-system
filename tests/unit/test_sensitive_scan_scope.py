"""The sensitive-value backstop is narrowed to run-derived fields only.

MERIDIAN's demo password is the literal word "password", which is also the
declared parameter name. Scanning the whole serialized blob made the *name*
look like leaked data, so no capability taking credentials could compile. The
scan now skips declared vocabulary (parameter names, their registry-authored
descriptions, and profile-authored error rules) and still scans everything else.

These tests exist to prove the narrowing did not open a hole: a real runtime
value in any value-bearing position must still be refused.
"""

import pytest

from tests.unit.test_compiler import compiler, make_run
from ui_capabilities.discovery.compiler import ArtifactCompiler
from ui_capabilities.models.errors import CompileError

SECRET = "M-10001"  # the bound member_id in the fixture run


def _artifact():
    return compiler().compile(make_run())


def test_clean_artifact_still_compiles():
    assert _artifact().capability_id == "member.get_savings_balance"


@pytest.mark.parametrize(
    "path",
    [
        ".steps[0].name",
        ".steps[0].target.description",
        ".steps[0].target.strategies[0].value",
        ".steps[0].target.strategies[0].name",
        ".steps[0].url_template",
        ".steps[0].checkpoint_after[0].value",
        ".steps[0].value.value",
        ".success_conditions[0].value",
        ".preconditions[0].value",
        ".description",
        ".name",
        ".target.entry_point",
        ".target.app_fingerprint.app_title",
        ".provenance.discovery_run_id",
        ".contract.outputs[0].source_step_id",
    ],
)
def test_value_positions_are_still_scanned(path):
    """Every field a runtime value could hide in remains in scope."""
    assert not ArtifactCompiler._declared_vocabulary(path), f"{path} must stay scanned"


@pytest.mark.parametrize(
    "path",
    [
        ".contract.inputs[0].name",
        ".contract.inputs[0].description",
        ".contract.outputs[0].name",
        ".contract.outputs[0].description",
        ".steps[1].value.name",
        ".error_rules[0].when[0].value",
        ".error_rules[2].caller_message",
    ],
)
def test_only_declared_vocabulary_is_exempt(path):
    assert ArtifactCompiler._declared_vocabulary(path)


def test_a_real_leak_in_a_literal_is_still_refused():
    artifact = _artifact()
    data = artifact.model_dump()
    data["steps"][0]["name"] = f"Click {SECRET} row"
    leaked = type(artifact).model_validate(data)
    with pytest.raises(CompileError, match="sensitive invocation value"):
        ArtifactCompiler._assert_no_sensitive_values(leaked, [SECRET])


def test_a_real_leak_in_a_condition_is_still_refused():
    artifact = _artifact()
    data = artifact.model_dump()
    data["success_conditions"][0]["value"] = f"/members/{SECRET}/accounts"
    leaked = type(artifact).model_validate(data)
    with pytest.raises(CompileError, match="sensitive invocation value"):
        ArtifactCompiler._assert_no_sensitive_values(leaked, [SECRET])


def test_a_real_leak_in_a_locator_is_still_refused():
    artifact = _artifact()
    data = artifact.model_dump()
    data["steps"][0]["target"]["strategies"][0]["value"] = SECRET
    leaked = type(artifact).model_validate(data)
    with pytest.raises(CompileError, match="sensitive invocation value"):
        ArtifactCompiler._assert_no_sensitive_values(leaked, [SECRET])


def test_the_error_message_names_the_offending_path():
    artifact = _artifact()
    data = artifact.model_dump()
    data["description"] = f"balance for {SECRET}"
    leaked = type(artifact).model_validate(data)
    with pytest.raises(CompileError, match=r"\.description"):
        ArtifactCompiler._assert_no_sensitive_values(leaked, [SECRET])


def test_vocabulary_collision_no_longer_blocks_compilation():
    """The MERIDIAN case: the demo password is the word "password", which is also
    the parameter name, the InputValueRef name, the registry description, and
    part of the target's own "Invalid operator ID or password." detector.

    None of those is run-derived data. Before the narrowing, all four counted as
    leaks and no capability taking credentials could compile at all.
    """
    from ui_capabilities.discovery.compiler import load_artifact

    artifact = load_artifact("artifacts/meridian/meridian.sign_on.v1.json")
    exempt = [
        p
        for p, _ in _walk(artifact)
        if ArtifactCompiler._declared_vocabulary(p)
    ]
    assert any(p.endswith(".name") and ".contract.inputs" in p for p in exempt)
    assert any(p.startswith(".error_rules") for p in exempt)


def test_credential_colliding_with_a_form_field_name_needs_explicit_credential_context():
    """Superseded by the narrow exemption added for this exact collision
    (see tests/unit/test_credential_locator_exemption.py and DECISIONS D024).

    MERIDIAN's password field is `name="password"`, so the durable locator
    `stable_attribute name=password` is byte-identical to the demo credential.
    `_assert_no_sensitive_values` now resolves this — but ONLY when the caller
    explicitly supplies `credential_values` naming it a declared credential.
    Called without that context (as any caller unaware of credentials would),
    the collision is indistinguishable from a real leak and is still refused —
    the safe default is "reject", not "silently allow".
    """
    from ui_capabilities.discovery.compiler import load_artifact

    artifact = load_artifact("artifacts/meridian/meridian.sign_on.v1.json")
    with pytest.raises(CompileError, match=r"strategies"):
        ArtifactCompiler._assert_no_sensitive_values(artifact, ["password"])  # no credential_values
    # supplying the credential context resolves exactly this artifact/value
    ArtifactCompiler._assert_no_sensitive_values(artifact, ["password"], frozenset({"password"}))


def _walk(artifact):
    import json

    def walk(node, path=""):
        if isinstance(node, dict):
            for key, item in node.items():
                yield from walk(item, f"{path}.{key}")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                yield from walk(item, f"{path}[{index}]")
        elif isinstance(node, str):
            yield path, node

    return list(walk(json.loads(artifact.model_dump_json())))
