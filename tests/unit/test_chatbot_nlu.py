"""P7: deterministic request understanding — the two demo-prioritized
requests plus representative coverage of the other capabilities. No network,
no model call: this is pure regex/keyword logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from ui_capabilities.api.catalog import CapabilityCatalog
from ui_capabilities.chatbot.nlu import (
    ask_for_missing_inputs,
    detect_capability,
    extract_member_search_freeform,
    extract_slots,
    is_cancel,
    required_business_inputs,
)

MERIDIAN_ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "meridian"


def test_balance_demo_request_maps_to_get_member_balances():
    text = "Check the balances for member 100234."
    capability_id = detect_capability(text)
    assert capability_id == "meridian.get_member_balances"
    slots = extract_slots(capability_id, text)
    assert slots == {"member_number": "100234"}


@pytest.mark.parametrize(
    "text",
    [
        "Check the balances for member 100234",
        "Check balance for member 100234",
        "Show balances for member 100234",
        "What are the balances for member 100234?",
        "Get balances for 100234",
        "Show member 100234 balances",
    ],
)
def test_balance_phrasing_variants_extract_member_number(text):
    capability_id = detect_capability(text)
    assert capability_id == "meridian.get_member_balances"
    slots = extract_slots(capability_id, text)
    assert slots == {"member_number": "100234"}, text


def test_balance_request_without_number_asks_only_for_member_number():
    text = "Check member balances"
    capability_id = detect_capability(text)
    assert capability_id == "meridian.get_member_balances"
    slots = extract_slots(capability_id, text)
    assert slots == {}
    artifact = CapabilityCatalog(MERIDIAN_ARTIFACTS_DIR).get(capability_id)
    missing = required_business_inputs(artifact)
    assert missing == ["member_number"]
    assert "member_number" not in ask_for_missing_inputs(artifact, missing, slots)


def test_transfer_demo_request_maps_to_funds_transfer_with_all_slots():
    text = "Transfer $1 from share 100234-S0001-12 to share 100234-MMKT-21 for member 100234."
    capability_id = detect_capability(text)
    assert capability_id == "meridian.funds_transfer"
    slots = extract_slots(capability_id, text)
    assert slots["member_number"] == "100234"
    assert slots["from_share"] == "100234-S0001-12"
    assert slots["to_share"] == "100234-MMKT-21"
    assert slots["amount"] == "1"


@pytest.mark.parametrize(
    "text,expected_amount",
    [
        ("Transfer $1 from 100234-S0001-12 to 100234-MMKT-21 for member 100234", "1"),
        ("Move $25 from 100234-S0001-12 to 100234-MMKT-21 for member 100234", "25"),
        ("Transfer 10 dollars between 100234-S0001-12 and 100234-MMKT-21 for member 100234", "10"),
    ],
)
def test_funds_transfer_natural_phrasing_extracts_actual_contract_fields(text, expected_amount):
    capability_id = detect_capability(text)
    assert capability_id == "meridian.funds_transfer"
    slots = extract_slots(capability_id, text)
    assert slots == {
        "member_number": "100234",
        "from_share": "100234-S0001-12",
        "to_share": "100234-MMKT-21",
        "amount": expected_amount,
    }


def test_funds_transfer_incomplete_request_leaves_missing_slots_pending():
    """Ambiguity rule: a capability can be identified and the member number
    extracted, but source/destination/amount must never be guessed."""
    text = "Transfer money for member 100234"
    capability_id = detect_capability(text)
    assert capability_id == "meridian.funds_transfer"
    slots = extract_slots(capability_id, text)
    assert slots == {"member_number": "100234"}
    artifact = CapabilityCatalog(MERIDIAN_ARTIFACTS_DIR).get(capability_id)
    missing = [n for n in required_business_inputs(artifact) if n not in slots]
    assert set(missing) == {"from_share", "to_share", "amount"}
    ask = ask_for_missing_inputs(artifact, missing, slots)
    for internal_name in ("from_share", "to_share", "amount"):
        assert internal_name not in ask


@pytest.mark.parametrize(
    "text",
    [
        "Open a new share for member 100234",
        "Open a share for member 100234",
        "Create a new share account for member 100234",
    ],
)
def test_open_share_natural_phrasing_extracts_member_number(text):
    capability_id = detect_capability(text)
    assert capability_id == "meridian.open_share"
    slots = extract_slots(capability_id, text)
    assert slots == {"member_number": "100234"}, text


def test_open_share_bare_request_leaves_share_details_pending():
    text = "Open a share"
    capability_id = detect_capability(text)
    assert capability_id == "meridian.open_share"
    slots = extract_slots(capability_id, text)
    assert slots == {}
    artifact = CapabilityCatalog(MERIDIAN_ARTIFACTS_DIR).get(capability_id)
    missing = required_business_inputs(artifact)
    assert set(missing) == {"member_number", "share_type", "initial_deposit"}


@pytest.mark.parametrize(
    "text",
    [
        "Update member 100234",
        "Update the address for member 100234",
        "Change member 100234's address",
        "Update member information for 100234",
    ],
)
def test_update_member_info_natural_phrasing_extracts_member_number_only(text):
    """None of these sentences state an actual new email/phone/address
    value, so nothing beyond `member_number` may be extracted — the update
    value itself must remain slot-filled, never invented."""
    capability_id = detect_capability(text)
    assert capability_id == "meridian.update_member_info"
    slots = extract_slots(capability_id, text)
    assert slots == {"member_number": "100234"}, text
    artifact = CapabilityCatalog(MERIDIAN_ARTIFACTS_DIR).get(capability_id)
    missing = [n for n in required_business_inputs(artifact) if n not in slots]
    assert set(missing) == {"email", "phone", "address"}
    ask = ask_for_missing_inputs(artifact, missing, slots)
    # a natural question, not a raw "field (description)" dump
    assert "mailing address" in ask.lower()
    assert "email address" in ask.lower()
    assert "(" not in ask


def test_place_hold_request_extracts_share_and_reason():
    text = "Place a hold on share 100234-S0001-12 for member 100234, reason FRAUD."
    capability_id = detect_capability(text)
    assert capability_id == "meridian.place_hold"
    slots = extract_slots(capability_id, text)
    assert slots["member_number"] == "100234"
    assert slots["share"] == "100234-S0001-12"
    assert slots["reason_code"] == "FRAUD"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Place a hold for member 100234", {"member_number": "100234"}),
        (
            "Put a hold on member 100234's account",
            {"member_number": "100234"},
        ),
    ],
)
def test_place_hold_natural_phrasing_extracts_only_clearly_present_fields(text, expected):
    capability_id = detect_capability(text)
    assert capability_id == "meridian.place_hold"
    slots = extract_slots(capability_id, text)
    assert slots == expected, text
    artifact = CapabilityCatalog(MERIDIAN_ARTIFACTS_DIR).get(capability_id)
    missing = [n for n in required_business_inputs(artifact) if n not in slots]
    assert set(missing) == {"share", "reason_code"}
    ask = ask_for_missing_inputs(artifact, missing, slots)
    assert "share" in ask.lower() and "reason" in ask.lower()


def test_member_inquiry_by_number():
    text = "Look up member 100234"
    capability_id = detect_capability(text)
    assert capability_id == "meridian.member_inquiry"
    slots = extract_slots(capability_id, text)
    assert slots == {"search_mode": "number", "search_value": "100234"}


def test_member_inquiry_by_last_name():
    text = "Look up the member with last name Lovelace"
    capability_id = detect_capability(text)
    assert capability_id == "meridian.member_inquiry"
    slots = extract_slots(capability_id, text)
    assert slots == {"search_mode": "name", "search_value": "Lovelace"}


@pytest.mark.parametrize(
    "text",
    [
        "Find member Lovelace",
        "Look up member Lovelace",
        "Find member by last name Lovelace",
        "Find member with last name Lovelace",
        "Find member with lastname Lovelace",
        "Search for member Lovelace",
    ],
)
def test_member_inquiry_name_phrasing_variants(text):
    capability_id = detect_capability(text)
    assert capability_id == "meridian.member_inquiry"
    slots = extract_slots(capability_id, text)
    assert slots == {"search_mode": "name", "search_value": "Lovelace"}, text


@pytest.mark.parametrize(
    "text",
    [
        "Find member 100234",
        "Look up member 100234",
        "Look up member number 100234",
        "Find member number 100234",
    ],
)
def test_member_inquiry_number_phrasing_variants(text):
    capability_id = detect_capability(text)
    assert capability_id == "meridian.member_inquiry"
    slots = extract_slots(capability_id, text)
    assert slots == {"search_mode": "number", "search_value": "100234"}, text


def test_member_inquiry_bare_request_extracts_nothing_and_asks():
    """'Find member' alone must not guess a search mode/value; the router
    asks the user rather than manufacturing one."""
    text = "Find member"
    capability_id = detect_capability(text)
    assert capability_id == "meridian.member_inquiry"
    slots = extract_slots(capability_id, text)
    assert slots == {}
    artifact = CapabilityCatalog(MERIDIAN_ARTIFACTS_DIR).get(capability_id)
    missing = [n for n in required_business_inputs(artifact) if n not in slots]
    ask = ask_for_missing_inputs(artifact, missing, slots)
    assert "search_mode" not in ask and "search_value" not in ask
    assert "member number" in ask.lower() and "last name" in ask.lower()


def test_member_search_freeform_reply_fills_both_slots_at_once():
    """After the combined 'member number or last name?' question, a bare
    reply like "Lovelace" (no word "member" at all) must resolve to a name
    search rather than leaving the bot stuck re-asking."""
    assert extract_member_search_freeform("Lovelace") == ("name", "Lovelace")
    assert extract_member_search_freeform("last name Lovelace") == ("name", "Lovelace")
    assert extract_member_search_freeform("   ") is None


def test_update_member_info_extracts_email_and_phone():
    text = "Update member 100234 with email ada@example.com and phone 555-1234"
    capability_id = detect_capability(text)
    assert capability_id == "meridian.update_member_info"
    slots = extract_slots(capability_id, text)
    assert slots["member_number"] == "100234"
    assert slots["email"] == "ada@example.com"
    assert slots["phone"] == "555-1234"


def test_open_share_extracts_type_and_deposit():
    text = "Open a new share MMKT for member 100234 with an initial deposit of $50"
    capability_id = detect_capability(text)
    assert capability_id == "meridian.open_share"
    slots = extract_slots(capability_id, text)
    assert slots["member_number"] == "100234"
    assert slots["share_type"] == "MMKT"
    assert slots["initial_deposit"] == "50"


def test_unrecognized_request_returns_none():
    assert detect_capability("what's the weather like today") is None


def test_cancel_words_detected():
    assert is_cancel("cancel")
    assert is_cancel("Never Mind")
    assert not is_cancel("cancel my transfer of $5")


def test_required_business_inputs_excludes_server_supplied_fields():
    catalog = CapabilityCatalog(MERIDIAN_ARTIFACTS_DIR)
    artifact = catalog.get("meridian.funds_transfer")
    required = required_business_inputs(artifact)
    assert "operator_id" not in required
    assert "password" not in required
    assert "branch" not in required
    assert set(required) == {"member_number", "from_share", "to_share", "amount"}
