"""Deterministic, obviously fictional member fixtures.

No real names, SSNs, or account numbers appear anywhere in this app.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Account:
    account_kind: str  # "Checking" | "Savings" | sub-account types
    slug: str  # stable id fragment used in legacy markup, e.g. "sav"
    balance: float
    status: str = "Active"


@dataclass
class Member:
    member_id: str
    display_name: str
    standing: str
    joined: str
    accounts: list[Account] = field(default_factory=list)
    # deterministic behavior knob per docs/08
    denies_subaccounts: bool = False


def seed_members() -> dict[str, Member]:
    return {
        "M-10001": Member(
            member_id="M-10001",
            display_name="Demo Member One",
            standing="Good",
            joined="2019-03-12",
            accounts=[
                Account("Checking", "chk", 1204.10),
                Account("Savings", "sav", 2540.75),
            ],
        ),
        "M-10002": Member(
            member_id="M-10002",
            display_name="Demo Member Two",
            standing="Review",
            joined="2015-11-02",
            denies_subaccounts=True,
            accounts=[
                Account("Checking", "chk", 88.00),
                Account("Savings", "sav", 10325.40),
            ],
        ),
        "M-10003": Member(
            member_id="M-10003",
            display_name="Demo Member Three",
            standing="Good",
            joined="2022-07-29",
            accounts=[
                Account("Checking", "chk", 412.33),
                Account("Savings", "sav", 87.12),
            ],
        ),
    }


MEMBER_ID_PATTERN = r"^M-\d{5}$"
