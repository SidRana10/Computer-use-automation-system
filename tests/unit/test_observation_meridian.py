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


def test_element_info_script_treats_hidden_inputs_as_visible():
    assert "type === 'hidden'" in _ELEMENT_INFO_JS


def test_bordered_table_gets_a_css_candidate_strategy():
    """MERIDIAN's shares/search-results tables carry no id, name, or label —
    only a legacy `border` attribute distinguishes them from layout tables
    (verified live: layout tables are border=0, data tables border=1). Without
    this, discovery has no way to address a variable-length table at all."""
    info = {"tag": "table", "type": None, "text": "Share ID Type Balance Status", "aria_label": None,
            "label": None, "name": None, "id": None, "placeholder": None, "options": [], "border": "1"}
    strategies = candidate_strategies("table", info)
    assert any(s.kind == "css" and s.value == 'table[border="1"]' for s in strategies)


def test_layout_table_without_border_gets_no_css_strategy():
    info = {"tag": "table", "type": None, "text": None, "aria_label": None, "label": None,
            "name": None, "id": None, "placeholder": None, "options": [], "border": None}
    strategies = candidate_strategies("table", info)
    assert strategies == []


def test_table_tag_maps_to_table_kind():
    from ui_capabilities.surfaces.observation import _element_kind

    assert _element_kind({"tag": "table"}) == "table"


def test_inventory_selector_scopes_tables_to_nonzero_border():
    from ui_capabilities.surfaces.observation import _INVENTORY_SELECTOR

    assert 'table[border]:not([border="0"])' in _INVENTORY_SELECTOR


def test_hidden_token_field_maps_to_hidden_kind():
    """A genuine discovery run against MERIDIAN's funds-transfer review page
    found the model unable to reference the hidden `_token` field at all: it
    is never visible (offsetWidth/offsetHeight/getClientRects are all zero by
    definition), and the inventory used to skip anything not visible. Without
    this, "explicitly extract the current hidden token" (P3) has no element
    to extract from."""
    from ui_capabilities.surfaces.observation import _element_kind

    assert _element_kind({"tag": "input", "type": "hidden"}) == "hidden"


def test_hidden_field_gets_a_stable_attribute_strategy_but_no_role_name():
    info = {"tag": "input", "type": "hidden", "text": None, "aria_label": None, "label": None,
            "name": "_token", "id": None, "placeholder": None, "options": []}
    strategies = candidate_strategies("hidden", info)
    kinds = [(s.kind.value, s.attribute, s.value) for s in strategies]
    assert ("stable_attribute", "name", "_token") in kinds
    assert not any(s.kind == "role_name" for s in strategies), "a hidden field has no accessible role"


def test_inventory_selector_includes_label_adjacent_value_cells():
    """A genuine `meridian.funds_transfer` discovery run reached the posted
    transaction receipt and could not extract the "Confirmation:" value at
    all: MERIDIAN renders it as a plain `<td>` with no id, and the inventory
    previously only enumerated cells carrying one. This is the identical
    structural pattern already verified live for screenshot masking
    (`td.lbl:text-is(...) + td`), just widened from masking into observation."""
    from ui_capabilities.surfaces.observation import _INVENTORY_SELECTOR

    assert "td.lbl + td" in _INVENTORY_SELECTOR


def test_inventory_selector_excludes_value_cells_wrapping_a_form_control():
    """A `td.lbl + td` cell that itself wraps an `<input>`/`<select>` is
    already reachable through that control's own selector; without this
    exclusion it would also surface as a second, redundant "cell" element."""
    from ui_capabilities.surfaces.observation import _INVENTORY_SELECTOR

    assert ":not(:has(input, select, textarea, a, button))" in _INVENTORY_SELECTOR


def test_element_info_script_detects_lbl_class_label_cells():
    assert "labelFromLblCell" in _ELEMENT_INFO_JS
    assert "classList.contains('lbl')" in _ELEMENT_INFO_JS


def test_result_cell_with_lbl_label_gets_a_css_candidate_strategy():
    """Mirrors the already-verified live selector `td.lbl:text-is("Confirmation:")
    + td` (D020's screenshot-mask list) rather than inventing a new one."""
    info = {"tag": "td", "type": None, "text": "TXN-000123", "aria_label": None,
            "label": "Confirmation", "label_from_lbl_cell": True,
            "name": None, "id": None, "placeholder": None, "options": []}
    strategies = candidate_strategies("cell", info)
    assert any(
        s.kind == "css" and s.value == 'td.lbl:text-is("Confirmation:") + td'
        for s in strategies
    )


def test_ordinary_cell_without_lbl_sibling_gets_no_css_strategy():
    """A `td[id]` cell whose label came from some other preceding cell (not
    one carrying MERIDIAN's `.lbl` class) must not get the CSS strategy —
    it is not the verified structural pattern the strategy is anchored on."""
    info = {"tag": "td", "type": None, "text": "some value", "aria_label": None,
            "label": "Some Field", "label_from_lbl_cell": False,
            "name": None, "id": "some-id", "placeholder": None, "options": []}
    strategies = candidate_strategies("cell", info)
    assert not any(s.kind == "css" for s in strategies)
