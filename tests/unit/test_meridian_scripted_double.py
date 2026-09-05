"""Offline coverage for the MERIDIAN scripted test double.

The double exists to exercise the real pipeline (discovery loop -> recorder ->
compiler -> replay) against MERIDIAN's markup without an API call. It is not,
and can never be, genuine discovery evidence. These tests drive it with
synthetic observations so it needs neither a browser nor the network.
"""

from ui_capabilities.discovery.fake_model import ScriptedMeridianSignOnModel
from ui_capabilities.discovery.model_adapter import TurnContext
from ui_capabilities.models.actions import ClickAction, DoneAction, FillAction, SelectAction
from ui_capabilities.policy.config import PolicyConfig
from ui_capabilities.surfaces.base import ObservedElement, Observation


def _signon_observation() -> Observation:
    return Observation(
        url="https://t/signon", path="/signon", title="Sign On - Meridian Core",
        heading="OPERATOR SIGN ON", visible_text_summary="", fingerprint="f",
        elements=[
            ObservedElement(ref="e1", kind="textbox", tag="input", name_attr="operator", label="Operator ID"),
            ObservedElement(ref="e2", kind="textbox", tag="input", name_attr="password", label="Password"),
            ObservedElement(ref="e3", kind="combobox", tag="select", name_attr="branch", label="Branch"),
            ObservedElement(ref="e4", kind="button", tag="input", accessible_name="Sign On", text="Sign On"),
        ],
    )


def _menu_observation() -> Observation:
    return Observation(
        url="https://t/menu", path="/menu", title="Main Menu - Meridian Core",
        heading="MAIN MENU", visible_text_summary="MAIN MENU", fingerprint="g", elements=[],
    )


def _context() -> TurnContext:
    return TurnContext(
        goal="sign on", target_app_name="MERIDIAN", entry_point="https://t",
        step_number=1, max_steps=20, elapsed_seconds=0, timeout_seconds=180,
        policy=PolicyConfig(allowed_domains=["t"], allowed_ports=[443],
                            allowed_route_patterns=["/**"], allowed_actions=["fill"]),
    )


async def test_it_drives_the_signon_form_by_field_name():
    """MERIDIAN has no ids or real labels, so `name` is the only identity."""
    model = ScriptedMeridianSignOnModel()
    obs, ctx = _signon_observation(), _context()

    first = await model.next_action(obs, ctx)
    assert isinstance(first, FillAction) and first.element_ref == "e1"
    assert first.value_source.input_name == "operator_id", "the executor binds the value, not the model"

    second = await model.next_action(obs, ctx)
    assert isinstance(second, FillAction) and second.value_source.input_name == "password"

    third = await model.next_action(obs, ctx)
    assert isinstance(third, SelectAction) and third.value_source.input_name == "branch"

    fourth = await model.next_action(obs, ctx)
    assert isinstance(fourth, ClickAction) and fourth.element_ref == "e4"


async def test_it_declares_done_only_on_the_main_menu():
    model = ScriptedMeridianSignOnModel()
    done = await model.next_action(_menu_observation(), _context())
    assert isinstance(done, DoneAction)
    assert done.suggested_success_condition.value == "MAIN MENU"


async def test_it_never_emits_a_literal_credential():
    """A double must not leak a value any more than a real provider would."""
    model = ScriptedMeridianSignOnModel()
    obs, ctx = _signon_observation(), _context()
    for _ in range(4):
        action = await model.next_action(obs, ctx)
        source = getattr(action, "value_source", None)
        if source is not None:
            assert source.literal is None
            assert source.input_name is not None


def test_it_is_labelled_as_a_test_double():
    assert ScriptedMeridianSignOnModel.name.startswith("fake-")
    assert "TEST DOUBLE" in ScriptedMeridianSignOnModel.__doc__
