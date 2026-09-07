"""P7: the chatbot HTTP loop — multi-turn slot filling, cancellation, and
explaining each of the four RunResult shapes in plain language. Built on the
same FakeRunner as the API route tests, through the real `CapabilityService`
and `build_app` wiring — the chatbot's only path to a result."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ui_capabilities.api.app import build_app
from ui_capabilities.chatbot.router import _business_result, _explain
from ui_capabilities.models.results import EscalatedResult, SuccessResult

from _api_test_support import make_service


def _success(artifact, inputs):
    return SuccessResult(
        run_id="chat-test-1",
        capability_id=artifact.capability_id,
        capability_version=artifact.capability_version,
        outputs={
            "shares": [
                {"Share ID": "100234-S0001", "Type": "Regular Shares", "Balance": "$2,499.00", "Status": "HOLD [HOLD]"},
                {"Share ID": "100234-MMKT-3", "Type": "Money Market", "Balance": "$11.00", "Status": "OPEN"},
            ]
        },
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
    assert len(runner.calls) == 1

    reply = body["reply"]
    # the useful business answer leads the reply, not a technical headline
    assert reply.startswith("Here are the member's balances:")
    # actual structured share rows are surfaced, not just a dashboard pointer
    assert "Type" in reply and "Balance" in reply and "Status" in reply
    assert "Regular Shares" in reply
    assert "$2,499.00" in reply
    assert "Money Market" in reply
    assert "OPEN" in reply
    # real row count, not hardcoded
    assert "2 share accounts found" in reply
    # the old generic list summary must not be used for `shares`
    assert "result(s)" not in reply
    assert "see the run's dashboard" not in reply
    # no share id/member-number-bearing identifier leaks into the chat reply
    assert "100234-S0001" not in reply
    # run id/dashboard link remain available, but as secondary metadata after
    # the business content, not the lead of the reply
    assert "chat-test-1" in reply
    assert "/dashboard/runs/chat-test-1" in reply
    assert reply.index("Run:") > reply.index("share accounts found")


def test_incomplete_transfer_request_asks_for_missing_fields_then_completes(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")
    client, runner = _client(tmp_path)

    first = client.post("/chatbot/message", json={"message": "Transfer money for member 100234"})
    body = first.json()
    assert body["result"] is None
    # conversational questions, not raw internal field names
    reply = body["reply"].lower()
    assert "share" in reply
    assert "how much" in reply
    assert "from_share" not in reply and "to_share" not in reply
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


def test_ambiguous_member_inquiry_asks_then_resolves_from_freeform_reply(tmp_path, monkeypatch):
    """'Find member' alone must not guess a mode/value; a bare follow-up
    reply like "Lovelace" (no internal field names, no repeated "member")
    then completes the request through the same CapabilityService path."""
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")

    def _member_found(artifact, inputs):
        return SuccessResult(
            run_id="chat-test-inquiry-freeform",
            capability_id=artifact.capability_id,
            capability_version=artifact.capability_version,
            outputs={"member_results": [{"Member No.": "100234", "Name": "Lovelace, Ada"}]},
        )

    client, runner = _client(tmp_path, _member_found)

    first = client.post("/chatbot/message", json={"message": "Find member"})
    body = first.json()
    assert body["result"] is None
    reply = body["reply"].lower()
    assert "member number" in reply and "last name" in reply
    assert "search_mode" not in reply and "search_value" not in reply
    session_id = body["session_id"]
    assert runner.calls == []

    second = client.post("/chatbot/message", json={"session_id": session_id, "message": "Lovelace"})
    body2 = second.json()
    assert body2["result"] is not None
    assert body2["result"]["status"] == "success"
    assert len(runner.calls) == 1
    _, bound_inputs = runner.calls[0]
    assert bound_inputs["search_mode"] == "name"
    assert bound_inputs["search_value"] == "Lovelace"
    assert "Member found:" in body2["reply"]


def test_open_share_natural_phrase_extracts_member_and_leaves_share_details_pending(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")
    client, runner = _client(tmp_path)

    response = client.post("/chatbot/message", json={"message": "Open a new share for member 100234"})
    body = response.json()
    assert body["result"] is None
    reply = body["reply"].lower()
    assert "share_type" not in reply and "initial_deposit" not in reply
    assert "share" in reply
    assert runner.calls == []


def test_update_member_info_natural_phrase_extracts_member_and_leaves_values_pending(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")
    client, runner = _client(tmp_path)

    response = client.post("/chatbot/message", json={"message": "Update the address for member 100234"})
    body = response.json()
    assert body["result"] is None
    reply = body["reply"].lower()
    assert "mailing address" in reply
    assert "email address" in reply and "phone number" in reply
    assert runner.calls == []


def test_place_hold_natural_phrase_extracts_member_and_leaves_required_fields_pending(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")
    client, runner = _client(tmp_path)

    response = client.post("/chatbot/message", json={"message": "Place a hold for member 100234"})
    body = response.json()
    assert body["result"] is None
    reply = body["reply"].lower()
    assert "reason_code" not in reply and "share" in reply and "reason" in reply
    assert runner.calls == []


def test_member_inquiry_single_match_renders_member_data(tmp_path, monkeypatch):
    """Member inquiry must show the actual returned member row, not a
    `member_results = 1 result(s) — see the dashboard` technical summary."""
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")

    def _single_match(artifact, inputs):
        return SuccessResult(
            run_id="chat-test-inquiry-1",
            capability_id=artifact.capability_id,
            capability_version=artifact.capability_version,
            outputs={"member_results": [{"Member No.": "100234", "Name": "Lovelace, Ada"}]},
        )

    client, runner = _client(tmp_path, _single_match)
    response = client.post("/chatbot/message", json={"message": "look up member with last name Lovelace"})
    body = response.json()
    assert body["result"]["status"] == "success"
    assert len(runner.calls) == 1

    reply = body["reply"]
    assert reply.startswith("Member found:")
    assert "100234" in reply
    assert "Lovelace, Ada" in reply
    assert "1 member found." in reply
    assert "result(s)" not in reply


def test_member_inquiry_multi_match_renders_all_members(tmp_path, monkeypatch):
    """Multi-match behavior must be preserved: every returned member row is
    shown, not collapsed to a bare count."""
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")

    def _multi_match(artifact, inputs):
        return SuccessResult(
            run_id="chat-test-inquiry-2",
            capability_id=artifact.capability_id,
            capability_version=artifact.capability_version,
            outputs={
                "member_results": [
                    {"Member No.": "100234", "Name": "Lovelace, Ada"},
                    {"Member No.": "100987", "Name": "Lovelace, Byron"},
                    {"Member No.": "101555", "Name": "Lovelace-Smith, Ada"},
                ]
            },
        )

    client, runner = _client(tmp_path, _multi_match)
    response = client.post("/chatbot/message", json={"message": "look up member with last name Lovelace"})
    body = response.json()
    assert body["result"]["status"] == "success"
    assert len(runner.calls) == 1

    reply = body["reply"]
    assert reply.startswith("Members found:")
    assert "100234" in reply and "Lovelace, Ada" in reply
    assert "100987" in reply and "Lovelace, Byron" in reply
    assert "101555" in reply and "Lovelace-Smith, Ada" in reply
    assert "3 members found." in reply


def test_member_inquiry_generic_columns_promote_header_row_and_drop_action_column(tmp_path, monkeypatch):
    """When MERIDIAN's table-header heuristic falls back to generic
    `col1..col4` keys (empty trailing header cell — see README Known
    limitations), the extraction leaks its own header caption row as an
    ordinary first row. The chatbot must promote that row into display
    headers, never count it as a member, and drop the blank-captioned
    "Select" action column."""
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")

    def _generic_columns(artifact, inputs):
        return SuccessResult(
            run_id="chat-test-inquiry-generic",
            capability_id=artifact.capability_id,
            capability_version=artifact.capability_version,
            outputs={
                "member_results": [
                    {"col1": "Member No.", "col2": "Name", "col3": "Shares", "col4": ""},
                    {"col1": "100234", "col2": "Lovelace, Ada", "col3": "42", "col4": "Select"},
                ]
            },
        )

    client, runner = _client(tmp_path, _generic_columns)
    response = client.post("/chatbot/message", json={"message": "look up member with last name Lovelace"})
    body = response.json()
    assert body["result"]["status"] == "success"
    assert len(runner.calls) == 1

    reply = body["reply"]
    assert reply.startswith("Member found:")
    # promoted headers, not raw generic keys
    assert "Member No." in reply and "Name" in reply and "Shares" in reply
    assert "col1" not in reply and "col2" not in reply
    # real member data present
    assert "100234" in reply and "Lovelace, Ada" in reply and "42" in reply
    # header row not counted as a member; action column dropped
    assert "1 member found." in reply
    assert "Select" not in reply


def test_member_inquiry_generic_columns_multiple_rows_report_correct_count(tmp_path, monkeypatch):
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")

    def _generic_columns_multi(artifact, inputs):
        return SuccessResult(
            run_id="chat-test-inquiry-generic-multi",
            capability_id=artifact.capability_id,
            capability_version=artifact.capability_version,
            outputs={
                "member_results": [
                    {"col1": "Member No.", "col2": "Name", "col3": "Shares", "col4": ""},
                    {"col1": "100234", "col2": "Lovelace, Ada", "col3": "42", "col4": "Select"},
                    {"col1": "100987", "col2": "Lovelace, Byron", "col3": "7", "col4": "Select"},
                ]
            },
        )

    client, runner = _client(tmp_path, _generic_columns_multi)
    response = client.post("/chatbot/message", json={"message": "look up member with last name Lovelace"})
    body = response.json()
    assert body["result"]["status"] == "success"

    reply = body["reply"]
    assert reply.startswith("Members found:")
    assert "100234" in reply and "Lovelace, Ada" in reply
    assert "100987" in reply and "Lovelace, Byron" in reply
    assert "2 members found." in reply
    assert "col1" not in reply
    assert "Select" not in reply


def test_successful_non_list_capability_returns_business_response(tmp_path, monkeypatch):
    """`place_hold` (like the other 4 write capabilities) declares no typed
    outputs at all — the chatbot must still lead with a plain-language
    statement of completion rather than a bare technical `succeeded` line,
    and must never fabricate data the capability didn't return."""
    monkeypatch.setenv("MERIDIAN_TELLER_ID", "teller1")
    monkeypatch.setenv("MERIDIAN_TELLER_PASSWORD", "s3cret")

    def _hold_success(artifact, inputs):
        return SuccessResult(
            run_id="chat-test-hold-1",
            capability_id=artifact.capability_id,
            capability_version=artifact.capability_version,
            outputs={},
        )

    client, runner = _client(tmp_path, _hold_success)
    response = client.post(
        "/chatbot/message",
        json={"message": "Place a hold on share 100234-S0001-12 for member 100234, reason FRAUD."},
    )
    body = response.json()
    assert body["result"]["status"] == "success"
    assert len(runner.calls) == 1
    reply = body["reply"]
    assert "hold" in reply.lower() and "placed" in reply.lower()
    assert "chat-test-hold-1" in reply
    assert "/dashboard/runs/chat-test-hold-1" in reply


def test_generic_unhandled_list_output_falls_back_to_count_summary():
    """A capability with no dedicated formatter (none of the current 7, but
    kept as a safety net) still gets the pre-existing count-and-dashboard
    summary rather than silently dropping its declared outputs."""
    business = _business_result(
        "meridian.some_future_capability",
        "Some Future Capability",
        {"widgets": [{"a": 1}, {"a": 2}, {"a": 3}]},
    )
    assert "3 result(s) — see the run's dashboard page for the full table" in business


def test_sign_on_reply_never_surfaces_credentials_or_tokens():
    """Sign-on has no typed outputs and must never leak the operator
    credentials/session it was invoked with into the chat reply."""
    result = SuccessResult(
        run_id="chat-test-signon",
        capability_id="meridian.sign_on",
        capability_version="1.0.0",
        outputs={},
    )
    reply = _explain(result, "Meridian Sign On")
    assert "signed on" in reply.lower()
    for forbidden in ("password", "token", "operator_id", "session", "teller1", "s3cret"):
        assert forbidden not in reply.lower()


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
    reply = body["reply"].lower()
    assert "share" in reply
    assert "how much" in reply
    assert "from_share" not in reply and "to_share" not in reply
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
    reply = body["reply"]
    assert "int-abc123" in reply
    assert "supervisor" in reply.lower()
    assert "This request requires supervisor sign-on." in reply
    # escalation must never read as a completed/successful operation
    assert "succeeded" not in reply.lower()
    assert "completed" not in reply.lower()
    assert "chat-test-escalated" in reply
    assert "/dashboard/runs/chat-test-escalated" in reply


def test_chat_page_does_not_duplicate_the_run_status_line(tmp_path):
    """The business-facing reply already carries the run id/dashboard path
    (`_run_metadata`); the chat page's own JS must not separately append a
    second 'run: ... (status: ...)' line for the same result."""
    client, _ = _client(tmp_path)
    response = client.get("/chatbot/")
    assert response.status_code == 200
    html = response.text
    assert "'run: '" not in html
    assert "data.result.run_id" not in html
    # the reply itself (which already carries the run id) is still rendered
    assert "data.reply" in html
