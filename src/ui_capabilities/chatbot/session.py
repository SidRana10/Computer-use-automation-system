"""In-memory, per-session slot-filling state for the chatbot.

A demo-scale conversational surface does not need a database or a durable
session store: state is small (one pending capability id + a handful of
collected string slots), lost on process restart exactly like the operator
console's in-memory `InterventionStore` already is, and never holds anything
that isn't about to become an ordinary capability invocation argument.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class ChatSession:
    pending_capability_id: str | None = None
    collected: dict[str, str] = field(default_factory=dict)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, ChatSession] = {}

    def get_or_create(self, session_id: str | None) -> tuple[str, ChatSession]:
        if session_id and session_id in self._sessions:
            return session_id, self._sessions[session_id]
        new_id = session_id or f"sess-{uuid.uuid4().hex[:10]}"
        session = self._sessions.setdefault(new_id, ChatSession())
        return new_id, session

    def reset(self, session_id: str) -> None:
        self._sessions[session_id] = ChatSession()
