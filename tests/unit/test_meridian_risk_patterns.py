"""Deterministic control-risk classification for the four MERIDIAN write
capabilities added in P2-P5.

Verified live against the real target (P2 recon): the transfer and hold
confirm screens both render an "IRREVERSIBLE ACTION" banner and their final
submit captions are "Post Transfer" / "Apply Hold". The open-share confirm
screen renders no such banner and its caption is "Open Share" — a real
product distinction (a new share can be closed later; a posted transfer or an
applied hold cannot) — so it is classified risky, not irreversible. The
update-member-information screen has no review step at all; its single
submit caption is "Save Changes", already classified risky in P1.
"""

from ui_capabilities.models.errors import RiskLevel
from ui_capabilities.targets import get_profile

ENTRY = "https://web-sample.interface-hiring.com"


def _policy():
    return get_profile("meridian").policy(ENTRY)


def test_post_transfer_and_apply_hold_are_irreversible():
    policy = _policy()
    assert policy is not None
    from ui_capabilities.policy.engine import PolicyEngine

    engine = PolicyEngine(policy)
    assert engine.classify_control_risk("Post Transfer") == RiskLevel.IRREVERSIBLE
    assert engine.classify_control_risk("Apply Hold") == RiskLevel.IRREVERSIBLE


def test_open_share_and_save_changes_are_risky_not_irreversible():
    from ui_capabilities.policy.engine import PolicyEngine

    engine = PolicyEngine(_policy())
    assert engine.classify_control_risk("Open Share") == RiskLevel.RISKY
    assert engine.classify_control_risk("Save Changes") == RiskLevel.RISKY


def test_unrelated_captions_stay_safe():
    from ui_capabilities.policy.engine import PolicyEngine

    engine = PolicyEngine(_policy())
    for caption in ("Search", "Continue", "Sign On", "Cancel", "Open New Share"):
        assert engine.classify_control_risk(caption) == RiskLevel.SAFE, caption
