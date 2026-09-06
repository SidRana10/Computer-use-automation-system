"""P7: deterministic request understanding — the two demo-prioritized
requests plus representative coverage of the other capabilities. No network,
no model call: this is pure regex/keyword logic."""

from __future__ import annotations

from pathlib import Path

from ui_capabilities.api.catalog import CapabilityCatalog
from ui_capabilities.chatbot.nlu import detect_capability, extract_slots, is_cancel, required_business_inputs

MERIDIAN_ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "meridian"


def test_balance_demo_request_maps_to_get_member_balances():
    text = "Check the balances for member 100234."
    capability_id = detect_capability(text)
    assert capability_id == "meridian.get_member_balances"
    slots = extract_slots(capability_id, text)
    assert slots == {"member_number": "100234"}


def test_transfer_demo_request_maps_to_funds_transfer_with_all_slots():
    text = "Transfer $1 from share 100234-S0001-12 to share 100234-MMKT-21 for member 100234."
    capability_id = detect_capability(text)
    assert capability_id == "meridian.funds_transfer"
    slots = extract_slots(capability_id, text)
    assert slots["member_number"] == "100234"
    assert slots["from_share"] == "100234-S0001-12"
    assert slots["to_share"] == "100234-MMKT-21"
    assert slots["amount"] == "1"


def test_place_hold_request_extracts_share_and_reason():
    text = "Place a hold on share 100234-S0001-12 for member 100234, reason FRAUD."
    capability_id = detect_capability(text)
    assert capability_id == "meridian.place_hold"
    slots = extract_slots(capability_id, text)
    assert slots["member_number"] == "100234"
    assert slots["share"] == "100234-S0001-12"
    assert slots["reason_code"] == "FRAUD"


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
