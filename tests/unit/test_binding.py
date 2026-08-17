import pytest

from tests.fixtures.factories import make_balance_artifact
from ui_capabilities.models.artifact import InputValueRef, LiteralValue
from ui_capabilities.replay import binder

ENTRY = "http://127.0.0.1:8001/"


def contract():
    return make_balance_artifact(ENTRY).contract


def test_bind_ok():
    bound = binder.validate_and_bind(contract(), {"member_id": "M-10003"})
    assert bound == {"member_id": "M-10003"}


def test_missing_required_input_rejected():
    with pytest.raises(binder.InvocationError, match="missing required"):
        binder.validate_and_bind(contract(), {})


def test_unknown_input_rejected():
    with pytest.raises(binder.InvocationError, match="unknown input"):
        binder.validate_and_bind(contract(), {"member_id": "M-10003", "extra": "x"})


def test_pattern_mismatch_rejected_before_any_browser_action():
    with pytest.raises(binder.InvocationError, match="pattern"):
        binder.validate_and_bind(contract(), {"member_id": "BAD"})


def test_type_validation():
    from ui_capabilities.models.artifact import CapabilityContract, InputSpec

    c = CapabilityContract(inputs=[InputSpec(name="n", type="integer", description="")], outputs=[])
    with pytest.raises(binder.InvocationError, match="integer"):
        binder.validate_and_bind(c, {"n": "abc"})
    assert binder.validate_and_bind(c, {"n": "42"}) == {"n": "42"}


def test_resolve_value_input_ref_and_literal():
    assert binder.resolve_value(InputValueRef(name="member_id"), {"member_id": "M-10001"}) == "M-10001"
    assert binder.resolve_value(LiteralValue(value="Holiday Savings"), {}) == "Holiday Savings"
    with pytest.raises(binder.InvocationError, match="not bound"):
        binder.resolve_value(InputValueRef(name="ghost"), {})


def test_render_url_template():
    url = binder.render_url("/members/{member_id}/accounts", {"member_id": "M-10001"}, ENTRY)
    assert url == "http://127.0.0.1:8001/members/M-10001/accounts"
    with pytest.raises(binder.InvocationError, match="unbound"):
        binder.render_url("/members/{ghost}", {}, ENTRY)


def test_coerce_output_money_and_types():
    assert binder.coerce_output("b", "$2,540.75", "decimal") == pytest.approx(2540.75)
    assert binder.coerce_output("n", "42", "integer") == 42
    assert binder.coerce_output("f", "yes", "boolean") is True
    with pytest.raises(binder.OutputCoercionError):
        binder.coerce_output("b", "no balance", "decimal")
