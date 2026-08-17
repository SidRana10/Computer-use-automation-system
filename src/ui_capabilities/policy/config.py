"""Typed, configurable policy. Effective policy is always the intersection
(strictest combination) of global and artifact policy."""

from __future__ import annotations

import re

from pydantic import BaseModel

from ..models.artifact import CapabilityPolicy
from ..models.errors import RiskLevel, stricter_risk


def route_pattern_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a glob-ish route pattern to a regex.

    `**` matches any path suffix (including `/`), `*` matches one path
    segment. Patterns anchor at the start of the path.
    """
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + r"/?$")


class PolicyConfig(BaseModel):
    allowed_domains: list[str]
    allowed_ports: list[int]
    allowed_route_patterns: list[str]
    allowed_actions: list[str]
    max_unattended_risk: RiskLevel = RiskLevel.REVERSIBLE
    require_human_for: list[RiskLevel] = [RiskLevel.RISKY, RiskLevel.IRREVERSIBLE]
    # Deterministic risk classification of controls by visible identity;
    # policy code, not the model, decides what counts as risky.
    irreversible_control_patterns: list[str] = ["confirm open account", "confirm transfer", "delete"]
    risky_control_patterns: list[str] = []
    max_wait_ms: int = 3000

    def narrowed_by(self, cap: CapabilityPolicy) -> "PolicyConfig":
        """Intersect with an artifact policy; the artifact can only narrow."""
        return PolicyConfig(
            allowed_domains=[d for d in self.allowed_domains if d in set(cap.allowed_domains)],
            allowed_ports=self.allowed_ports,
            # keep a capability route pattern only when the global policy
            # already admits it (literally, or as a narrowing of a global glob)
            allowed_route_patterns=[
                p
                for p in cap.allowed_route_patterns
                if p in set(self.allowed_route_patterns) or _pattern_within(p, self.allowed_route_patterns)
            ],
            allowed_actions=[a for a in self.allowed_actions if a in set(cap.allowed_actions)],
            max_unattended_risk=stricter_risk(self.max_unattended_risk, cap.max_unattended_risk),
            require_human_for=sorted(
                set(self.require_human_for) | set(cap.require_human_for), key=lambda r: r.value
            ),
            irreversible_control_patterns=self.irreversible_control_patterns,
            risky_control_patterns=self.risky_control_patterns,
            max_wait_ms=self.max_wait_ms,
        )


_PROBE = "uicapprobe"


def _probe_paths(pattern: str) -> list[str]:
    """Representative concrete paths the pattern can match, derived from its
    own glob semantics (`**` spans any suffix, `*` spans one segment)."""
    if "**" in pattern:
        expansions = ["", _PROBE, f"{_PROBE}/{_PROBE}b"]
        candidates = [pattern.replace("**", exp) for exp in expansions]
    else:
        candidates = [pattern]
    return [c.replace("*", _PROBE) for c in candidates]


def _pattern_within(candidate: str, allowed: list[str]) -> bool:
    """True only if EVERY concrete path the candidate can match is also
    admitted by some global pattern.

    A capability may narrow global route privileges, never broaden them, so
    containment is decided by the route-pattern semantics themselves — never
    by a literal string prefix, which would let `/anything/**` slip through
    whenever the global policy allows `/`.
    """
    regexes = [route_pattern_to_regex(g) for g in allowed]
    probes = _probe_paths(candidate)
    return bool(probes) and all(any(r.match(probe) for r in regexes) for probe in probes)


def default_demo_policy(target_base_url: str = "http://127.0.0.1:8001") -> PolicyConfig:
    from urllib.parse import urlparse

    parsed = urlparse(target_base_url)
    return PolicyConfig(
        allowed_domains=[parsed.hostname or "127.0.0.1", "localhost"],
        allowed_ports=[parsed.port or 80],
        allowed_route_patterns=["/", "/members/**", "/session/**", "/demo-note"],
        allowed_actions=["navigate", "click", "fill", "select", "extract", "wait_for", "assert", "wait"],
        max_unattended_risk=RiskLevel.REVERSIBLE,
        require_human_for=[RiskLevel.RISKY, RiskLevel.IRREVERSIBLE],
    )
