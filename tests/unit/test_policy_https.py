"""HTTPS targets must be reachable, and Northstar policy must not shift.

The Phase-1 policy derived `allowed_ports` as `parsed.port or 80`, while
`PolicyEngine.check_url` resolves an https URL with no explicit port to 443.
Every MERIDIAN URL was therefore PORT_BLOCKED.
"""

from ui_capabilities.policy.config import default_demo_policy, default_port_for
from ui_capabilities.policy.engine import PolicyEngine
from ui_capabilities.targets import get_profile

MERIDIAN = "https://web-sample.interface-hiring.com"


def test_default_port_is_scheme_aware():
    assert default_port_for(MERIDIAN) == 443
    assert default_port_for("http://127.0.0.1:8001") == 8001
    assert default_port_for("http://example.test") == 80
    assert default_port_for("https://example.test:8443") == 8443


def test_meridian_https_urls_are_allowed():
    engine = PolicyEngine(get_profile("meridian").policy())
    for path in ("/signon", "/menu", "/members", "/members/100234", "/members/100234/transfer"):
        decision = engine.check_url(f"{MERIDIAN}{path}")
        assert decision.allowed, f"{path} blocked: {decision.code} {decision.reason}"


def test_meridian_policy_still_fails_closed_off_target():
    engine = PolicyEngine(get_profile("meridian").policy())
    assert not engine.check_url("https://evil.example.com/menu").allowed
    assert not engine.check_url("https://web-sample.interface-hiring.com:9443/menu").allowed
    assert not engine.check_url("file:///etc/passwd").allowed


def test_fault_injection_console_is_not_on_the_automated_surface():
    """`/settings` is operator tooling, the same line Northstar draws at /demo/**."""
    engine = PolicyEngine(get_profile("meridian").policy())
    decision = engine.check_url(f"{MERIDIAN}/settings")
    assert not decision.allowed and decision.code == "ROUTE_BLOCKED"


def test_northstar_policy_is_byte_identical_to_phase_one():
    """The Northstar profile must delegate to the original factory unchanged."""
    profile = get_profile("northstar")
    assert profile.policy("http://127.0.0.1:8001") == default_demo_policy("http://127.0.0.1:8001")
    assert default_demo_policy().allowed_ports == [80] or default_demo_policy().allowed_ports == [8001]
