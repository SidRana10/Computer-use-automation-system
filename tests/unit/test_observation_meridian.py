"""Observation fixes proven necessary by the live MERIDIAN markup.

The target renders no `id`, `aria-label`, `data-*` or `<label>` elements, and
captions its submit buttons with `value`. Without these fixes the model sees
three anonymous textboxes and an anonymous button.
"""

from ui_capabilities.discovery.prompts import element_inventory_json
from ui_capabilities.surfaces.base import ObservedElement, Observation
from ui_capabilities.surfaces.observation import _ELEMENT_INFO_JS, candidate_strategies


def test_submit_value_becomes_the_control_caption():
    info = {"tag": "input", "type": "submit", "text": "Sign On", "aria_label": None, "label": None,
            "name": None, "id": None, "placeholder": None, "options": []}
    strategies = candidate_strategies("button", info)
    assert any(s.kind == "role_name" and s.name == "Sign On" for s in strategies)


def test_name_attribute_is_a_durable_strategy_when_nothing_else_exists():
    info = {"tag": "input", "type": "text", "text": None, "aria_label": None, "label": None,
            "name": "operator", "id": None, "placeholder": None, "options": []}
    strategies = candidate_strategies("textbox", info)
    kinds = [(s.kind.value, s.attribute, s.value) for s in strategies]
    assert ("stable_attribute", "name", "operator") in kinds


def test_inventory_exposes_stable_attributes_to_the_model():
    """Three anonymous textboxes are indistinguishable without `name`."""
    obs = Observation(
        url="https://t/signon", path="/signon", title="Sign On", visible_text_summary="",
        fingerprint="f",
        elements=[
            ObservedElement(ref="e1", kind="textbox", tag="input", name_attr="operator"),
            ObservedElement(ref="e2", kind="textbox", tag="input", name_attr="password"),
            ObservedElement(ref="e3", kind="combobox", tag="select", name_attr="branch",
                            options=["MAIN-001 - Main Office"], option_values=["MAIN-001"]),
        ],
    )
    payload = element_inventory_json(obs)
    assert '"name_attr": "operator"' in payload
    assert '"name_attr": "password"' in payload
    assert '"option_values"' in payload, "captions embed live data; values are the stable identity"


def test_element_info_script_reads_legacy_table_labels_and_submit_values():
    """The script is static and trusted; assert the two behaviours it gained."""
    assert "isValueCaptioned" in _ELEMENT_INFO_JS
    assert "previousElementSibling" in _ELEMENT_INFO_JS
    assert "optionValues" in _ELEMENT_INFO_JS
    for banned in ("eval(", "Function(", "fetch("):
        assert banned not in _ELEMENT_INFO_JS
