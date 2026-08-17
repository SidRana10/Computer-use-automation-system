import pytest

from tests.fixtures.factories import make_balance_artifact
from tests.fixtures.fakes import FakeSurface
from ui_capabilities.models.errors import ErrorClassification
from ui_capabilities.replay.error_classifier import classify_current_state

ENTRY = "http://127.0.0.1:8001/"


@pytest.fixture
def artifact():
    return make_balance_artifact(ENTRY)


async def test_not_found_text_maps_to_business_outcome(tmp_path, artifact):
    surface = FakeSurface(tmp_path, page_text="No member was found for that identifier.")
    rule = await classify_current_state(surface, artifact)
    assert rule is not None
    assert rule.code == "MEMBER_NOT_FOUND"
    assert rule.classification == ErrorClassification.BUSINESS_OUTCOME


async def test_validation_text_maps_to_business_outcome(tmp_path, artifact):
    surface = FakeSurface(tmp_path, page_text="Member ID must match M-#####.")
    rule = await classify_current_state(surface, artifact)
    assert rule.code == "VALIDATION_REJECTED"


async def test_interstitial_maps_to_recoverable_with_dismiss(tmp_path, artifact):
    surface = FakeSurface(tmp_path, page_text="Your session has been idle. Continue session?")
    rule = await classify_current_state(surface, artifact)
    assert rule.code == "KNOWN_INTERSTITIAL"
    assert rule.classification == ErrorClassification.RECOVERABLE
    assert rule.recovery[0].kind == "dismiss"
    assert rule.max_attempts == 2


async def test_session_expired_maps_to_hard_failure(tmp_path, artifact):
    surface = FakeSurface(tmp_path, page_text="Your session has expired. Please sign in again.")
    rule = await classify_current_state(surface, artifact)
    assert rule.code == "SESSION_EXPIRED"
    assert rule.classification == ErrorClassification.HARD_FAILURE


async def test_unknown_state_matches_no_rule(tmp_path, artifact):
    surface = FakeSurface(tmp_path, page_text="Something entirely unexpected")
    rule = await classify_current_state(surface, artifact)
    assert rule is None
