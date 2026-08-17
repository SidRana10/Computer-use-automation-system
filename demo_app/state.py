"""In-process mutable demo state with deterministic exception knobs.

All exceptional states are explicit flags set through /demo/config (local demo
tooling, not part of the automated surface's policy allowlist) so evidence
runs are reproducible rather than random.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .data import Member, seed_members


@dataclass
class PendingSubAccount:
    account_type: str
    nickname: str


@dataclass
class DemoState:
    members: dict[str, Member] = field(default_factory=seed_members)
    # one-shot: show idle-session interstitial on next Accounts view
    interstitial_pending: bool = False
    # one-shot: show transient loading page on next Accounts view
    slow_accounts_pending: bool = False
    # persistent until reset: remove the Accounts control from member summary
    failure_mode: str | None = None  # "missing_accounts_control"
    # persistent until reset: all member-area pages render session expired
    session_expired: bool = False
    pending_subaccounts: dict[str, PendingSubAccount] = field(default_factory=dict)
    confirmation_seq: int = 41

    def reset(self) -> None:
        self.members = seed_members()
        self.interstitial_pending = False
        self.slow_accounts_pending = False
        self.failure_mode = None
        self.session_expired = False
        self.pending_subaccounts = {}
        self.confirmation_seq = 41

    def next_confirmation_number(self) -> str:
        self.confirmation_seq += 1
        return f"SUB-{self.confirmation_seq:05d}"


STATE = DemoState()
