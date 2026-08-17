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
  if (el.id) {
    const lab = document.querySelector('label[for="' + el.id + '"]');
    if (lab) labelText = lab.innerText.trim();
  }
  if (!labelText && el.closest('label')) labelText = el.closest('label').innerText.trim();
  let options = [];
  if (tag === 'select') {
    options = Array.from(el.options).map(o => o.label || o.value).slice(0, 20);
  }
  const text = (el.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 80);
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
    options: options,
    visible: !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length)
  };
}
"""

_INVENTORY_SELECTOR = "a[href], button, input, select, textarea, [role='button'], td[id], th[id]"

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
        return "textbox"
    if tag in ("td", "th"):
        return "cell"
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
