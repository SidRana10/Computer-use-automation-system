"""A navigation that lands outside the policy allowlist (e.g. an injected
redirect) must become a POLICY_BLOCKED hard failure, not a silent continue."""

from tests.fixtures.factories import make_balance_artifact
from tests.fixtures.fakes import FakeSurface
from ui_capabilities.config import Settings
from ui_capabilities.observability.evidence import EvidenceManager
from ui_capabilities.observability.logger import RunLogger
from ui_capabilities.policy.config import default_demo_policy
from ui_capabilities.policy.engine import PolicyEngine
from ui_capabilities.policy.redaction import Redactor
from ui_capabilities.replay.engine import ReplayEngine

ENTRY = "http://127.0.0.1:8001/"


async def test_offsite_redirect_after_navigate_is_policy_blocked(tmp_path):
    artifact = make_balance_artifact(ENTRY)
    artifact.target.app_fingerprint = {}  # skip fingerprint observation in fake

    surface = FakeSurface(tmp_path)
    surface.redirects["http://127.0.0.1:8001/members/search"] = "https://evil.example.com/phish"

    settings = Settings(evidence_dir=tmp_path / "evidence")
    evidence = EvidenceManager(settings.evidence_dir, "redir-test")
    redactor = Redactor()
    engine = ReplayEngine(
        surface=surface,
        global_policy=PolicyEngine(default_demo_policy(ENTRY)),
        settings=settings,
        logger=RunLogger(evidence.log_path, redactor, "redir-test"),
        evidence=evidence,
        redactor=redactor,
    )
    result = await engine.replay(artifact, {"member_id": "M-10003"})
    assert result.status == "failure"
    assert result.code == "POLICY_BLOCKED"
    assert result.step_id == "s1_navigate"
    assert "outside policy" in result.observed
