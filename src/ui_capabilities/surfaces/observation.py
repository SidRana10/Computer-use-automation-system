"""Semantic element inventory: a compact, bounded description of the
interactive surface, with ephemeral refs and candidate durable locator
strategies. The LLM never invents selectors — the adapter owns them."""

from __future__ import annotations

import hashlib

from playwright.async_api import ElementHandle, Page

from ..models.targets import LocatorKind, LocatorStrategy
from .base import ObservedElement

# Static, trusted metadata script — never model-generated.
_ELEMENT_INFO_JS = """
(el) => {
  const tag = el.tagName.toLowerCase();
  let labelText = null;
  let labelFromLblCell = false;
  if (el.id) {
    const lab = document.querySelector('label[for="' + el.id + '"]');
    if (lab) labelText = lab.innerText.trim();
  }
  if (!labelText && el.closest('label')) labelText = el.closest('label').innerText.trim();
  // Legacy table layouts carry the field label in the preceding cell rather
  // than in a <label> element; fall back to it when nothing else names the
  // control. Bounded in length so a data cell can never become a label. When
  // `el` is itself a plain value <td> (not a form control), `el.closest('td')`
  // returns `el` itself, so this also names a read-only result cell — e.g. the
  // "Confirmation:" value on a posted-transaction receipt — the same
  // structural pattern already relied on for screenshot masking.
  if (!labelText) {
    const cell = el.closest('td');
    const prev = cell && cell.previousElementSibling;
    if (prev && prev.tagName === 'TD' && !prev.querySelector('input,select,textarea,a,button')) {
      const t = (prev.innerText || '').trim().replace(/\\s+/g, ' ').replace(/:$/, '');
      if (t && t.length <= 40) {
        labelText = t;
        labelFromLblCell = prev.classList.contains('lbl');
      }
    }
  }
  // A legacy bordered <table> is the only durable identity a variable-length
  // data table (a share list, a search-results set) offers: it carries no id
  // or class, but the `border` attribute is a stable structural marker
  // already used to scope screenshot masking to this exact element.
  const border = tag === 'table' ? el.getAttribute('border') : null;
  let options = [];
  let optionValues = [];
  if (tag === 'select') {
    options = Array.from(el.options).map(o => o.label || o.value).slice(0, 20);
    // Legacy option captions embed live data (e.g. a balance); the submitted
    // `value` is the stable identity, so both are recorded.
    optionValues = Array.from(el.options).map(o => o.value).slice(0, 20);
  }
  // input[type=submit|button] renders its caption in `value`, not innerText.
  const isValueCaptioned = tag === 'input' && ['submit', 'button', 'reset'].includes(el.type);
  const rawText = isValueCaptioned ? (el.value || '') : (el.innerText || '');
  const text = rawText.trim().replace(/\\s+/g, ' ').slice(0, 80);
  return {
    tag: tag,
    type: el.getAttribute('type'),
    role: el.getAttribute('role'),
    aria_label: el.getAttribute('aria-label'),
    id: el.id || null,
    name: el.getAttribute('name'),
    placeholder: el.getAttribute('placeholder'),
    text: text || null,
    label: labelText,
    label_from_lbl_cell: labelFromLblCell,
    options: options,
    option_values: optionValues,
    border: border,
    // A rendered element must have layout; a hidden form field never does
    // (offsetWidth/offsetHeight/getClientRects are all zero by definition),
    // yet a legacy write flow can carry a security/transaction token in
    // exactly such a field with no other way to observe it. It is listed
    // explicitly rather than folded into the ordinary visibility check, so a
    // capability can still only ever *fill* or *click* what a person could
    // actually see and act on.
    visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length) ||
      (tag === 'input' && el.type === 'hidden')
  };
}
"""

# `table[border="N"]` is scoped to bordered data tables only, so ordinary
# layout tables (border="0" on this target) never clutter the inventory.
# `td.lbl + td` is the same read-only label/value row pattern already relied
# on for screenshot masking (e.g. "Member:", "Confirmation:") — a plain
# result cell with no id/name/label of its own, addressable only by its
# preceding label cell's class and text. `:not(:has(...))` keeps this to pure
# display cells: a value cell that itself wraps a form control is already
# reachable through that control's own selector below, and would otherwise
# show up twice.
_INVENTORY_SELECTOR = (
    "a[href], button, input, select, textarea, [role='button'], td[id], th[id], "
    'table[border]:not([border="0"]), '
    "td.lbl + td:not(:has(input, select, textarea, a, button))"
)

MAX_ELEMENTS = 40
MAX_TEXT_SUMMARY = 900


def _element_kind(info: dict) -> str:
    tag = info["tag"]
    if tag == "a":
        return "link"
    if tag == "button" or info.get("role") == "button" or (tag == "input" and info.get("type") in ("submit", "button")):
        return "button"
    if tag == "select":
        return "combobox"
    if tag == "textarea":
        return "textbox"
    if tag == "input":
        if info.get("type") == "checkbox":
            return "checkbox"
        if info.get("type") == "radio":
            return "radio"
        if info.get("type") == "hidden":
            return "hidden"
        return "textbox"
    if tag in ("td", "th"):
        return "cell"
    if tag == "table":
        return "table"
    return tag


def _accessible_name(kind: str, info: dict) -> str | None:
    if info.get("aria_label"):
        return info["aria_label"]
    if kind in ("link", "button"):
        return info.get("text")
    return info.get("label")


def candidate_strategies(kind: str, info: dict) -> list[LocatorStrategy]:
    """Ordered candidate strategies, most robust first (docs/03 priority)."""
    out: list[LocatorStrategy] = []
    name = _accessible_name(kind, info)
    role = {"link": "link", "button": "button", "combobox": "combobox", "textbox": "textbox", "checkbox": "checkbox", "cell": "cell"}.get(kind)
    if role and name and kind in ("link", "button", "combobox", "textbox", "checkbox"):
        out.append(LocatorStrategy(kind=LocatorKind.ROLE_NAME, role=role, name=name))
    if info.get("label"):
        out.append(LocatorStrategy(kind=LocatorKind.LABEL, value=info["label"]))
    if info.get("placeholder"):
        out.append(LocatorStrategy(kind=LocatorKind.PLACEHOLDER, value=info["placeholder"]))
    if kind in ("link", "button") and info.get("text"):
        out.append(LocatorStrategy(kind=LocatorKind.TEXT, value=info["text"]))
    if info.get("name"):
        out.append(LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="name", value=info["name"]))
    if info.get("id"):
        out.append(LocatorStrategy(kind=LocatorKind.STABLE_ATTRIBUTE, attribute="id", value=info["id"]))
    if kind == "table" and info.get("border") is not None:
        # Last-resort structural identity (docs/03 CSS-last priority): a
        # variable-length legacy data table carries no id/name/label at all.
        out.append(LocatorStrategy(kind=LocatorKind.CSS, value=f'table[border="{info["border"]}"]'))
    if kind == "cell" and info.get("label_from_lbl_cell") and info.get("label"):
        # Last-resort structural identity for a read-only result cell (docs/03
        # CSS-last priority): the preceding LABEL strategy targets a real
        # <label> element and will not resolve here, so a value cell like
        # MERIDIAN's "Confirmation:" row needs its own anchor. Reuses the
        # exact selector shape already verified live for screenshot masking
        # (`td.lbl:text-is("X:") + td`) rather than inventing a new one.
        escaped = str(info["label"]).replace("\\", "\\\\").replace('"', '\\"')
        out.append(LocatorStrategy(kind=LocatorKind.CSS, value=f'td.lbl:text-is("{escaped}:") + td'))
    return out


async def build_inventory(page: Page) -> tuple[list[ObservedElement], dict[str, ElementHandle]]:
    handles = await page.query_selector_all(_INVENTORY_SELECTOR)
    elements: list[ObservedElement] = []
    ref_handles: dict[str, ElementHandle] = {}
    index = 0
    for handle in handles:
        if index >= MAX_ELEMENTS:
            break
        try:
            info = await handle.evaluate(_ELEMENT_INFO_JS)
        except Exception:
            continue
        if not info or not info.get("visible"):
            continue
        kind = _element_kind(info)
        ref = f"e{index + 1}"
        elements.append(
            ObservedElement(
                ref=ref,
                kind=kind,
                tag=info["tag"],
                accessible_name=_accessible_name(kind, info),
                label=info.get("label"),
                placeholder=info.get("placeholder"),
                text=info.get("text"),
                name_attr=info.get("name"),
                id_attr=info.get("id"),
                options=info.get("options") or [],
                option_values=info.get("option_values") or [],
                candidate_strategies=candidate_strategies(kind, info),
            )
        )
        ref_handles[ref] = handle
        index += 1
    return elements, ref_handles


async def visible_text_summary(page: Page) -> str:
    try:
        text = await page.inner_text("body", timeout=2000)
    except Exception:
        return ""
    collapsed = " ".join(text.split())
    return collapsed[:MAX_TEXT_SUMMARY]


def observation_fingerprint(path: str, title: str, elements: list[ObservedElement], text_summary: str) -> str:
    basis = "|".join(
        [path, title]
        + sorted(f"{e.kind}:{e.accessible_name or e.text or e.id_attr or ''}" for e in elements)
        + [text_summary[:200]]
    )
    return hashlib.sha1(basis.encode()).hexdigest()[:16]
