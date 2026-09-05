"""Registry of known target applications.

The Northstar profile deliberately delegates to the existing Phase-1 modules
(`policy.config.default_demo_policy`, `discovery.profiles.demo_app_error_rules`)
rather than re-homing them: the original implementation stays exactly where it
was and keeps its behavior, and the registry simply names it alongside the new
MERIDIAN profile.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from ..models.artifact import ErrorRule, InputSpec
from ..policy.config import PolicyConfig, default_demo_policy


@dataclass(frozen=True)
class TargetProfile:
    """Everything target-specific, in one place."""

    app_id: str
    vendor_family: str
    display_name: str
    default_entry_point: str
    policy_factory: Callable[[str], PolicyConfig]
    error_rules_factory: Callable[[], list[ErrorRule]]
    input_specs: dict[str, InputSpec] = field(default_factory=dict)
    # Which element names a page. Targets disagree: Northstar's <h1> is a fixed
    # banner and its content heading is <h2>; MERIDIAN uses <h1> per screen.
    heading_selector: str = "h2"
    # Marker extractors run against an observation to build the app fingerprint.
    title_marker: str = ""
    version_pattern: re.Pattern[str] | None = None
    # Durable-evidence redaction.
    screenshot_mask_selectors: tuple[str, ...] = ()
    redaction_text_patterns: tuple[str, ...] = ()
    # Playwright traces are raw captures: action parameters, request bodies,
    # unmasked frame images and verbatim DOM. Nothing in the redaction path
    # reaches inside a trace, so a target whose screens carry regulated data
    # turns durable tracing off rather than writing evidence it cannot sanitize.
    durable_traces: bool = True
    # Inputs the operator environment supplies; never requested from a caller.
    credential_inputs: tuple[str, ...] = ()

    def policy(self, entry_point: str | None = None) -> PolicyConfig:
        return self.policy_factory(entry_point or self.default_entry_point)

    def fingerprint(self, title: str, visible_text: str) -> dict[str, str]:
        fp = {"app_title": title}
        if self.version_pattern is not None:
            match = self.version_pattern.search(visible_text)
            if match:
                fp["build_marker"] = match.group(1)
        return fp

    def spec_for(self, name: str) -> InputSpec | None:
        return self.input_specs.get(name)


def _northstar() -> TargetProfile:
    from ..discovery.profiles import demo_app_error_rules

    return TargetProfile(
        app_id="northstar_member_servicing_demo",
        vendor_family="northstar_servicing",
        display_name="Northstar Credit Union — Member Servicing Console (Demo)",
        default_entry_point="http://127.0.0.1:8001",
        policy_factory=default_demo_policy,
        error_rules_factory=demo_app_error_rules,
        input_specs={
            "member_id": InputSpec(
                name="member_id",
                type="string",
                sensitive=True,
                pattern=r"M-\d{5}",
                description="Member identifier in the demo format M-#####",
            ),
            "account_type": InputSpec(
                name="account_type",
                type="string",
                description="Sub-account product type as shown in the console",
            ),
        },
        heading_selector="h2",
        title_marker="Northstar Credit Union",
        version_pattern=re.compile(r"Build ([\w.\-]+)"),
    )


def _meridian() -> TargetProfile:
    from .meridian import MERIDIAN_PROFILE

    return MERIDIAN_PROFILE


_BUILDERS: dict[str, Callable[[], TargetProfile]] = {
    "northstar": _northstar,
    "meridian": _meridian,
}

_CACHE: dict[str, TargetProfile] = {}


def profile_names() -> Sequence[str]:
    return tuple(_BUILDERS)


def get_profile(name: str) -> TargetProfile:
    key = (name or "").strip().lower()
    if key not in _BUILDERS:
        raise KeyError(f"unknown target profile {name!r}; known profiles: {list(_BUILDERS)}")
    if key not in _CACHE:
        _CACHE[key] = _BUILDERS[key]()
    return _CACHE[key]


def profile_for_app_id(app_id: str) -> TargetProfile | None:
    for name in _BUILDERS:
        profile = get_profile(name)
        if profile.app_id == app_id:
            return profile
    return None
