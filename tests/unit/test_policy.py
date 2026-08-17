from ui_capabilities.models.artifact import CapabilityPolicy
from ui_capabilities.models.errors import RiskLevel
from ui_capabilities.policy.config import default_demo_policy
from ui_capabilities.policy.engine import PolicyEngine


def engine() -> PolicyEngine:
    return PolicyEngine(default_demo_policy("http://127.0.0.1:8001"))


def test_allowed_local_route_accepted():
    decision = engine().check_action("navigate", url="http://127.0.0.1:8001/members/search")
    assert decision.allowed and not decision.requires_human


def test_external_domain_blocked_before_execution():
    decision = engine().check_action("navigate", url="https://evil.example.com/exfiltrate")
    assert not decision.allowed
    assert decision.code == "DOMAIN_BLOCKED"


def test_disallowed_scheme_blocked():
    decision = engine().check_url("file:///etc/passwd")
    assert not decision.allowed
    assert decision.code == "SCHEME_BLOCKED"


def test_route_outside_allowlist_blocked():
    decision = engine().check_url("http://127.0.0.1:8001/admin/secret")
    assert not decision.allowed
    assert decision.code == "ROUTE_BLOCKED"


def test_wrong_port_blocked():
    decision = engine().check_url("http://127.0.0.1:9999/members/search")
    assert not decision.allowed
    assert decision.code == "PORT_BLOCKED"


def test_unsupported_action_kind_blocked():
    decision = engine().check_action("evaluate_js")
    assert not decision.allowed
    assert decision.code == "ACTION_BLOCKED"


def test_irreversible_step_risk_requires_human():
    decision = engine().check_action("click", risk=RiskLevel.IRREVERSIBLE)
    assert not decision.allowed
    assert decision.requires_human
    assert decision.code == "HUMAN_APPROVAL_REQUIRED"


def test_irreversible_control_text_requires_human_even_if_risk_understated():
    decision = engine().check_action("click", risk=RiskLevel.SAFE, control_text="Confirm Open Account")
    assert decision.requires_human


def test_human_approved_irreversible_allowed():
    decision = engine().check_action("click", risk=RiskLevel.IRREVERSIBLE, human_approved=True)
    assert decision.allowed


def test_artifact_policy_cannot_broaden_global():
    base = default_demo_policy("http://127.0.0.1:8001")
    greedy = CapabilityPolicy(
        allowed_domains=["127.0.0.1", "evil.example.com"],
        allowed_route_patterns=["/members/**", "/session/**"],
        allowed_actions=["navigate", "click", "fill", "select", "extract", "wait_for", "assert", "evaluate_js"],
        max_unattended_risk=RiskLevel.IRREVERSIBLE,
        require_human_for=[],
    )
    narrowed = base.narrowed_by(greedy)
    assert "evil.example.com" not in narrowed.allowed_domains
    assert "evaluate_js" not in narrowed.allowed_actions
    assert narrowed.max_unattended_risk == RiskLevel.REVERSIBLE
    assert RiskLevel.IRREVERSIBLE in narrowed.require_human_for

    narrowed_engine = PolicyEngine(narrowed)
    assert not narrowed_engine.check_url("https://evil.example.com/x").allowed
    assert not narrowed_engine.check_action("click", risk=RiskLevel.IRREVERSIBLE).allowed


def test_artifact_policy_can_narrow_routes():
    base = default_demo_policy("http://127.0.0.1:8001")
    narrow = CapabilityPolicy(
        allowed_domains=["127.0.0.1"],
        allowed_route_patterns=["/members/**"],
        allowed_actions=["navigate", "click"],
        max_unattended_risk=RiskLevel.SAFE,
        require_human_for=[RiskLevel.RISKY, RiskLevel.IRREVERSIBLE],
    )
    narrowed = base.narrowed_by(narrow)
    e = PolicyEngine(narrowed)
    assert e.check_url("http://127.0.0.1:8001/members/search").allowed
    assert not e.check_action("fill").allowed
