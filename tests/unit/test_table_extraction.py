"""Structured table extraction.

MERIDIAN members hold a variable number of shares (30 and 11 were observed on
two seed members), and a last-name inquiry returns a variable number of rows.
Neither can be modelled as a fixed set of scalar outputs.
"""

import json

import pytest

from ui_capabilities.replay import binder


def test_json_output_is_parsed_into_structured_rows():
    raw = json.dumps(
        [
            {"Share ID": "100234-S0001", "Type": "Regular Shares", "Balance": "$2,499.00", "Status": "HOLD"},
            {"Share ID": "100234-MMKT-11", "Type": "Money Market", "Balance": "$80.01", "Status": "OPEN"},
        ]
    )
    rows = binder.coerce_output("shares", raw, "json")
    assert isinstance(rows, list) and len(rows) == 2
    assert rows[0]["Share ID"] == "100234-S0001"
    assert rows[1]["Status"] == "OPEN"


def test_variable_row_counts_are_fine():
    for count in (0, 1, 11, 30):
        rows = binder.coerce_output("shares", json.dumps([{"i": str(i)} for i in range(count)]), "json")
        assert len(rows) == count


def test_malformed_table_payload_fails_loudly():
    with pytest.raises(binder.OutputCoercionError, match="not valid JSON"):
        binder.coerce_output("shares", "<table>oops</table>", "json")


def test_scalar_coercion_is_unchanged():
    assert binder.coerce_output("bal", "$2,540.75", "decimal") == 2540.75
    assert binder.coerce_output("n", "17", "integer") == 17
    assert binder.coerce_output("s", " CN480296 ", "string") == "CN480296"
