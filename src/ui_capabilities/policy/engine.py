"""PolicyEngine: deterministic gate every proposed action passes through
before the surface executes it — in discovery and in replay alike.

The model proposes; this code decides.
"""

from __future__ import annotations

from urllib.parse import urlparse

from pydantic import BaseModel

from ..models.errors import RiskLevel, risk_exceeds
from .config import PolicyConfig, route_pattern_to_regex


class PolicyDecision(BaseModel):
    allowed: bool
    requires_human: bool = False
    code: str = "ALLOWED"
    reason: str = ""


class PolicyEngine:
    def __init__(self, config: PolicyConfig):
        self.config = config

    # -- URL / navigation ---------------------------------------------------

    def check_url(self, url: str) -> PolicyDecision:
        parsed = urlparse(url)
        if parsed.scheme and parsed.scheme not in ("http", "https"):
            return PolicyDecision(allowed=False, code="SCHEME_BLOCKED", reason=f"scheme {parsed.scheme!r} not permitted")
        host = (parsed.hostname or "").lower()
        if parsed.scheme:  # absolute URL: host must be allowlisted
            if host not in [d.lower() for d in self.config.allowed_domains]:
                return PolicyDecision(allowed=False, code="DOMAIN_BLOCKED", reason=f"host {host!r} not in allowlist")
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            if self.config.allowed_ports and port not in self.config.allowed_ports:
                return PolicyDecision(allowed=False, code="PORT_BLOCKED", reason=f"port {port} not in allowlist")
        path = parsed.path or "/"
        if not any(route_pattern_to_regex(p).match(path) for p in self.config.allowed_route_patterns):
            return PolicyDecision(allowed=False, code="ROUTE_BLOCKED", reason=f"route {path!r} not in allowed route patterns")
        return PolicyDecision(allowed=True)

    # -- Risk classification -------------------------------------------------

    def classify_control_risk(self, control_text: str | None) -> RiskLevel:
        """Deterministic text-based risk classification of a control.
        Used in discovery (where no artifact risk annotation exists yet) and as
        a floor in replay (declared step risk can only raise it)."""
        if not control_text:
            return RiskLevel.SAFE
        lowered = control_text.strip().lower()
        for pat in self.config.irreversible_control_patterns:
            if pat in lowered:
                return RiskLevel.IRREVERSIBLE
        for pat in self.config.risky_control_patterns:
            if pat in lowered:
                return RiskLevel.RISKY
        return RiskLevel.SAFE

    # -- Action gate ---------------------------------------------------------

    def check_action(
        self,
        action_kind: str,
        *,
        url: str | None = None,
        risk: RiskLevel = RiskLevel.SAFE,
        control_text: str | None = None,
        human_approved: bool = False,
    ) -> PolicyDecision:
        if action_kind not in self.config.allowed_actions:
            return PolicyDecision(allowed=False, code="ACTION_BLOCKED", reason=f"action kind {action_kind!r} not permitted")

        if url is not None:
            url_decision = self.check_url(url)
            if not url_decision.allowed:
                return url_decision

        effective_risk = risk
        heuristic = self.classify_control_risk(control_text)
        if risk_exceeds(heuristic, effective_risk):
            effective_risk = heuristic

        if effective_risk in self.config.require_human_for and not human_approved:
            return PolicyDecision(
                allowed=False,
                requires_human=True,
                code="HUMAN_APPROVAL_REQUIRED",
                reason=f"{effective_risk.value} action requires a human operator",
            )
        if risk_exceeds(effective_risk, self.config.max_unattended_risk) and not human_approved:
            return PolicyDecision(
                allowed=False,
                requires_human=True,
                code="HUMAN_APPROVAL_REQUIRED",
                reason=f"risk {effective_risk.value} exceeds unattended ceiling {self.config.max_unattended_risk.value}",
            )
        return PolicyDecision(allowed=True)
