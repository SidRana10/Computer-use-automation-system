"""P7: the chatbot HTTP loop — multi-turn slot filling, cancellation, and
explaining each of the four RunResult shapes in plain language. Built on the
same FakeRunner as the API route tests, through the real `CapabilityService`
and `build_app` wiring — the chatbot's only path to a result."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ui_capabilities.api.app import build_app
from ui_capabilities.models.results import EscalatedResult, SuccessResult

from _api_test_support import make_service


def _success(artifact, inputs):
    return SuccessResult(
        run_id="chat-test-1",
        capability_id=artifact.capability_id,
        capability_version=artifact.capability_version,
        outputs={"shares": [{"share": "100234-S0001-12", "balance": "1,234.56"}]},
    )


def _client(tmp_path, result_fn=_success):
    service, runner = make_service(tmp_path, result_fn)
    return TestClient(build_app(service)), runner


def test_complete_balance_request_invokes_immediately(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")
    client, runner = _client(tmp_path)

    response = client.post("/chatbot/message", json={"message": "Check the balances for member 100234."})
    assert response.status_code == 200
    body = response.json()
    assert body["result"] is not None
    assert body["result"]["status"] == "success"
    assert "succeeded" in body["reply"].lower()
    assert len(runner.calls) == 1


def test_incomplete_transfer_request_asks_for_missing_fields_then_completes(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")
    client, runner = _client(tmp_path)

    first = client.post("/chatbot/message", json={"message": "Transfer money for member 100234"})
    body = first.json()
    assert body["result"] is None
    assert "from_share" in body["reply"]
    assert "amount" in body["reply"]
    session_id = body["session_id"]
    assert runner.calls == []

    second = client.post(
        "/chatbot/message",
        json={
            "session_id": session_id,
            "message": "from share 100234-S0001-12 to share 100234-MMKT-21 for $1",
        },
    )
    body2 = second.json()
    assert body2["result"] is not None
    assert body2["result"]["status"] == "success"
    assert len(runner.calls) == 1
    _, bound_inputs = runner.calls[0]
    assert bound_inputs["member_number"] == "100234"
    assert bound_inputs["from_share"] == "100234-S0001-12"
    assert bound_inputs["to_share"] == "100234-MMKT-21"
    assert bound_inputs["amount"] == "1"


def test_free_text_address_fills_last_outstanding_slot(tmp_path, monkeypatch):
    """`address` matches none of nlu.py's extraction patterns, so once it is
    the only slot left outstanding the bot must accept the next raw message
    as its value instead of re-asking forever (P0 fix: chatbot update-member
    slot filling could previously loop indefinitely)."""
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")
    client, runner = _client(tmp_path)

    first = client.post(
        "/chatbot/message",
        json={"message": "update member 100234 email to a@b.com phone 555-1234"},
    )
    body = first.json()
    assert body["result"] is None
    assert "address" in body["reply"].lower()
    session_id = body["session_id"]
    assert runner.calls == []

    second = client.post(
        "/chatbot/message",
        json={"session_id": session_id, "message": "42 Elm Street, Springfield"},
    )
    body2 = second.json()
    assert body2["result"] is not None
    assert body2["result"]["status"] == "success"
    assert len(runner.calls) == 1
    _, bound_inputs = runner.calls[0]
    assert bound_inputs["address"] == "42 Elm Street, Springfield"
    assert bound_inputs["email"] == "a@b.com"
    assert bound_inputs["phone"] == "555-1234"


def test_cancel_resets_previously_collected_slots(tmp_path):
    client, runner = _client(tmp_path)
    first = client.post("/chatbot/message", json={"message": "Transfer money for member 100234"})
    session_id = first.json()["session_id"]

    # collect from_share/to_share before cancelling
    second = client.post(
        "/chatbot/message",
        json={"session_id": session_id, "message": "from share 100234-S0001-12 to share 100234-MMKT-21"},
    )
    assert second.json()["result"] is None  # amount still missing

    cancel = client.post("/chatbot/message", json={"session_id": session_id, "message": "cancel"})
    assert "starting over" in cancel.json()["reply"].lower()

    # a fresh transfer request must re-ask for from_share/to_share/amount —
    # none of the pre-cancel slots may have survived.
    followup = client.post(
        "/chatbot/message", json={"session_id": session_id, "message": "Transfer money for member 555555"}
    )
    body = followup.json()
    assert body["result"] is None
    assert "from_share" in body["reply"]
    assert "to_share" in body["reply"]
    assert "amount" in body["reply"]
    assert runner.calls == []


def test_unrecognized_request_lists_available_capabilities(tmp_path):
    client, _ = _client(tmp_path)
    response = client.post("/chatbot/message", json={"message": "what's the weather like"})
    body = response.json()
    assert body["result"] is None
    assert "get_member_balances" in body["reply"] or "Balances" in body["reply"]


def test_escalated_result_is_explained_clearly(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")

    def _escalated(artifact, inputs):
        return EscalatedResult(
            run_id="chat-test-escalated",
            capability_id=artifact.capability_id,
            capability_version=artifact.capability_version,
            code="SUPERVISOR_REQUIRED",
            intervention_id="int-abc123",
            message="This request requires supervisor sign-on.",
        )

    client, runner = _client(tmp_path, _escalated)
    response = client.post(
        "/chatbot/message",
        json={"message": "Place a hold on share 100234-S0001-12 for member 100234, reason FRAUD."},
    )
    body = response.json()
    assert body["result"]["status"] == "escalated"
    assert "int-abc123" in body["reply"]
    assert "human" in body["reply"].lower() or "supervisor" in body["reply"].lower()
