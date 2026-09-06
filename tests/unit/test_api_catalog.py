"""P6: the capability catalog reads the real, committed MERIDIAN artifacts
and exposes a caller-safe schema — no credential inputs, correct counts."""

from __future__ import annotations

from pathlib import Path

import pytest

from ui_capabilities.api.catalog import CapabilityCatalog, CapabilityNotFoundError
from ui_capabilities.api.schemas import to_detail, to_summary

MERIDIAN_ARTIFACTS_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "meridian"

EXPECTED_CAPABILITY_IDS = {
    "meridian.sign_on",
    "meridian.member_inquiry",
    "meridian.get_member_balances",
    "meridian.funds_transfer",
    "meridian.open_share",
    "meridian.update_member_info",
    "meridian.place_hold",
}


@pytest.fixture(scope="module")
def catalog() -> CapabilityCatalog:
    return CapabilityCatalog(MERIDIAN_ARTIFACTS_DIR)


def test_catalog_lists_exactly_the_seven_meridian_capabilities(catalog: CapabilityCatalog):
    ids = {a.capability_id for a in catalog.list()}
    assert ids == EXPECTED_CAPABILITY_IDS


def test_unknown_capability_id_raises(catalog: CapabilityCatalog):
    with pytest.raises(CapabilityNotFoundError):
        catalog.get("meridian.does_not_exist")


def test_public_schema_excludes_credential_inputs(catalog: CapabilityCatalog):
    artifact = catalog.get("meridian.get_member_balances")
    detail = to_detail(artifact, "MERIDIAN CORE")
    names = {i.name for i in detail.inputs}
    assert names == {"member_number"}
    assert "operator_id" not in names
    assert "password" not in names
    assert "branch" not in names


def test_public_schema_input_count_excludes_credentials(catalog: CapabilityCatalog):
    artifact = catalog.get("meridian.funds_transfer")
    summary = to_summary(artifact, "MERIDIAN CORE")
    # contract has 8 inputs total (amount, branch, from_share, member_number,
    # memo, operator_id, password, to_share); 3 are server-supplied.
    assert summary.input_count == len(artifact.contract.inputs) - 3


def test_capability_detail_surfaces_risk_and_escalation_metadata(catalog: CapabilityCatalog):
    place_hold = to_detail(catalog.get("meridian.place_hold"), "MERIDIAN CORE")
    assert place_hold.risk_level == "irreversible"
    assert "SUPERVISOR_REQUIRED" in place_hold.escalate_on_codes
