import pytest
from fastapi.testclient import TestClient

from demo_app.app import app
from demo_app.state import STATE


@pytest.fixture(autouse=True)
def reset_state():
    STATE.reset()
    yield
    STATE.reset()


@pytest.fixture
def client():
    return TestClient(app)


def test_search_flow_and_balance_visible(client):
    page = client.get("/members/search?member_id=M-10001", follow_redirects=True)
    assert "Member Summary" in page.text
    accounts = client.get("/members/M-10001/accounts")
    assert 'id="acct-sav-balance"' in accounts.text
    assert "$2540.75" in accounts.text or "$2,540.75" in accounts.text


def test_member_not_found_message_is_stable(client):
    page = client.get("/members/search?member_id=M-40400")
    assert "No member was found for that identifier." in page.text


def test_validation_rejection_message_is_stable(client):
    page = client.get("/members/search?member_id=BAD")
    assert "Member ID must match M-#####." in page.text


def test_permission_denied_for_m10002_subaccounts(client):
    page = client.get("/members/M-10002/subaccounts/new")
    assert "You do not have permission to open sub-accounts for this member." in page.text


def test_interstitial_shows_once_then_clears(client):
    STATE.interstitial_pending = True
    page = client.get("/members/M-10001/accounts")
    assert "Your session has been idle. Continue session?" in page.text
    cont = client.post("/session/continue", data={"next": "/members/M-10001/accounts"}, follow_redirects=True)
    assert "Savings" in cont.text
    assert not STATE.interstitial_pending


def test_transient_load_shows_once(client):
    STATE.slow_accounts_pending = True
    page = client.get("/members/M-10001/accounts")
    assert "Accounts are loading." in page.text
    page2 = client.get("/members/M-10001/accounts")
    assert "Savings" in page2.text


def test_missing_accounts_control_injection(client):
    STATE.failure_mode = "missing_accounts_control"
    page = client.get("/members/M-10001")
    assert 'href="/members/M-10001/accounts"' not in page.text
    assert "Accounts (temporarily unavailable)" in page.text


def test_session_expired_state(client):
    STATE.session_expired = True
    page = client.get("/members/M-10001/accounts")
    assert "Your session has expired." in page.text


def test_subaccount_review_confirm_flow(client):
    review = client.post("/members/M-10001/subaccounts/review", data={"account_type": "Holiday Savings", "nickname": ""})
    assert "Review New Sub-Account" in review.text
    assert "Confirm Open Account" in review.text
    confirmed = client.post("/members/M-10001/subaccounts/confirm", follow_redirects=True)
    assert "Sub-account opened successfully." in confirmed.text
    assert "SUB-000" in confirmed.text


def test_demo_reset(client):
    STATE.failure_mode = "missing_accounts_control"
    client.post("/demo/reset")
    assert STATE.failure_mode is None
