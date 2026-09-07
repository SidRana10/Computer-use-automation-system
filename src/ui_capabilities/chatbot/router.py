"""Thin chatbot: understand -> pick a capability -> fill typed args -> call
`CapabilityService.invoke` -> explain the structured result in plain
language.

This module never imports a surface, the replay engine, or Playwright — it
only ever calls the same `CapabilityService` the HTTP capability API uses
(`api/service.py`), so there is exactly one invocation path in the process,
not a chatbot-shaped shortcut around it.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..api.catalog import CapabilityNotFoundError
from ..api.service import CapabilityService, InvalidArgumentsError
from ..models.results import BusinessOutcomeResult, EscalatedResult, FailureResult, RunResult, SuccessResult
from .nlu import (
    ask_for_missing_inputs,
    detect_capability,
    extract_member_search_freeform,
    extract_slots,
    is_cancel,
    required_business_inputs,
)
from .session import SessionStore

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class ChatMessage(BaseModel):
    session_id: str | None = None
    message: str


class ChatReply(BaseModel):
    session_id: str
    reply: str
    result: RunResult | None = None


def _format_output(value: object) -> str:
    """A list-shaped output with no capability-specific formatter below is a
    lot of text for a chat reply; summarize it by count and point the reader
    at the dashboard for the full structured detail rather than dumping
    every row."""
    if isinstance(value, list):
        return f"{len(value)} result(s) — see the run's dashboard page for the full table"
    return str(value)


def _format_balance_rows(shares: list[object]) -> str:
    """Render `meridian.get_member_balances`'s `shares` rows as a small
    plain-text table (Type / Balance / Status only — no share id/member
    number in the chat reply) instead of the generic '<n> result(s) — see
    the dashboard' summary every other list-shaped output still gets."""
    header = f"{'Type':<24}{'Balance':>12}   {'Status'}"
    lines = [header]
    for row in shares:
        row_type = str(row.get("Type", "")) if isinstance(row, dict) else ""
        balance = str(row.get("Balance", "")) if isinstance(row, dict) else ""
        status = str(row.get("Status", "")) if isinstance(row, dict) else ""
        lines.append(f"{row_type:<24}{balance:>12}   {status}")
    return "\n".join(lines)


_GENERIC_COL_KEY_RE = re.compile(r"^col\d+$", re.IGNORECASE)


def _uses_generic_column_keys(row: dict[str, object]) -> bool:
    return bool(row) and all(_GENERIC_COL_KEY_RE.match(str(k)) for k in row.keys())


def _looks_like_header_row(row: dict[str, object]) -> bool:
    """True when a row's own values read like column captions rather than
    data — e.g. "Member No." where a genuine row starts with a numeric
    member number. Used only to detect MERIDIAN's header row leaking into
    `member_inquiry`'s output when its extraction falls back to generic
    `col1`/`col2`/… keys (see README Known limitations); it never affects
    the underlying extraction result, only how the chatbot displays it."""
    values = list(row.values())
    first_value = str(values[0]).strip() if values else ""
    return bool(first_value) and not first_value.isdigit()


def _prepare_member_rows(rows: list[object]) -> list[dict[str, object]]:
    """`member_inquiry`-only display cleanup: when the extraction fell back
    to generic `col1..colN` keys and the first row is actually MERIDIAN's
    own table header (not a member), promote it into column captions for
    every remaining row and drop it from the data — it must never be
    counted as a match. A trailing column whose caption is blank (the
    unlabeled "Select" action-link column) is dropped from the display,
    since it carries no member data. Rows that already use meaningful keys
    (the extraction's normal header-detection path) pass through
    untouched."""
    dict_rows = [r for r in rows if isinstance(r, dict)]
    if not dict_rows:
        return dict_rows
    header_row = dict_rows[0]
    if not (_uses_generic_column_keys(header_row) and _looks_like_header_row(header_row)):
        return dict_rows
    caption_by_key = {k: str(v).strip() for k, v in header_row.items() if str(v).strip()}
    return [{caption_by_key[k]: row.get(k, "") for k in caption_by_key} for row in dict_rows[1:]]


def _format_row_table(rows: list[object]) -> str:
    """Render a list of dict rows as an aligned plain-text table using
    exactly the field names the capability's own extraction returned —
    never relabeled or invented. Used for outputs with no dedicated
    formatter above (currently `member_inquiry`'s results).

    MERIDIAN's table extraction names columns from the page's own header
    row when it can; when that heuristic doesn't fire (e.g. a header with an
    empty trailing cell, as on the member-inquiry results table — see
    `README.md` Known limitations) it falls back to generic `col1`, `col2`,
    … names, and the header text itself shows up as an ordinary first row.
    This renderer displays whatever keys/values are actually present either
    way rather than guessing semantic labels that aren't in the typed
    output.
    """
    dict_rows = [r for r in rows if isinstance(r, dict)]
    if not dict_rows:
        return "\n".join(str(r) for r in rows) if rows else "(no rows returned)"
    keys = list(dict_rows[0].keys())
    widths = {k: max(len(str(k)), *(len(str(r.get(k, ""))) for r in dict_rows)) for k in keys}
    header = "  ".join(str(k).ljust(widths[k]) for k in keys)
    body = ["  ".join(str(r.get(k, "")).ljust(widths[k]) for k in keys) for r in dict_rows]
    return "\n".join([header, *body])


# Plain-language success statements for capabilities whose contract declares
# no typed outputs at all (`funds_transfer`, `open_share`, `update_member_info`,
# `place_hold`, `sign_on` — see `artifacts/meridian/*.v1.json`
# `contract.outputs`). Nothing here is invented per-invocation data; each is
# a static, capability-level statement of what a `success` status means.
_SUCCESS_MESSAGES: dict[str, str] = {
    "meridian.sign_on": "Signed on to MERIDIAN.",
    "meridian.funds_transfer": (
        "The funds transfer completed. (This capability does not return a "
        "confirmation number — see the run's evidence in the dashboard for "
        "the MERIDIAN confirmation screen.)"
    ),
    "meridian.open_share": "The new share was opened.",
    "meridian.update_member_info": "The member's information was updated.",
    "meridian.place_hold": "The hold was placed.",
}


def _business_result(capability_id: str, capability_name: str, outputs: dict[str, object]) -> str:
    """The business-facing answer for a successful invocation: the useful
    result first, built only from fields the capability actually returned —
    never invented balances, confirmation numbers, or member data."""
    if capability_id == "meridian.get_member_balances":
        shares = outputs.get("shares")
        if isinstance(shares, list):
            count = "1 share account" if len(shares) == 1 else f"{len(shares)} share accounts"
            return f"Here are the member's balances:\n\n{_format_balance_rows(shares)}\n\n{count} found."
    if capability_id == "meridian.member_inquiry":
        rows = outputs.get("member_results")
        if not isinstance(rows, list):
            rows = outputs.get("member_results_table")
        if isinstance(rows, list):
            display_rows = _prepare_member_rows(rows)
            if len(display_rows) == 1:
                headline, count_line = "Member found:", "1 member found."
            else:
                headline, count_line = "Members found:", f"{len(display_rows)} members found."
            return f"{headline}\n\n{_format_row_table(display_rows)}\n\n{count_line}"
    headline = _SUCCESS_MESSAGES.get(capability_id, f"{capability_name} completed successfully.")
    if outputs:
        # Defensive fallback for a capability with no dedicated formatter
        # above whose contract nonetheless declares outputs (none of the
        # current 7 do, besides the two handled explicitly) — keep the
        # existing summarize-by-count behavior rather than silently
        # dropping the data.
        details = "; ".join(f"{k} = {_format_output(v)}" for k, v in outputs.items())
        return f"{headline} ({details})"
    return headline


def _run_metadata(run_id: str) -> str:
    """Secondary observability metadata: run id and a direct dashboard path,
    always available but never the lead of a reply."""
    return f"Run: {run_id}\nView full run details in the dashboard: /dashboard/runs/{run_id}"


def _explain(result: RunResult, capability_name: str) -> str:
    if isinstance(result, SuccessResult):
        business = _business_result(result.capability_id, capability_name, result.outputs)
        return f"{business}\n\n{_run_metadata(result.run_id)}"
    if isinstance(result, BusinessOutcomeResult):
        return f"{result.message}\n\n{_run_metadata(result.run_id)}\nOutcome code: {result.code}"
    if isinstance(result, EscalatedResult):
        if result.code == "SUPERVISOR_REQUIRED":
            headline = "This operation requires supervisor authorization and has been paused for review."
        else:
            headline = "This operation requires human approval before continuing and has been paused."
        return (
            f"{headline}\n{result.message}\n\n"
            f"Intervention: {result.intervention_id}\n"
            f"{_run_metadata(result.run_id)}"
        )
    if isinstance(result, FailureResult):
        return f"Something went wrong: {result.observed or result.code}\n\n{_run_metadata(result.run_id)}"
    return f"{capability_name} finished with an unrecognized result shape."  # unreachable: RunResult is a closed union


def _catalog_help(service: CapabilityService) -> str:
    names = [
        f'"{a.name}" ({a.capability_id})' for a in service.catalog.list() if a.capability_id != "meridian.sign_on"
    ]
    return "I can help with: " + "; ".join(names) + "."


def build_chatbot_router(service: CapabilityService) -> APIRouter:
    router = APIRouter(prefix="/chatbot", tags=["chatbot"])
    sessions = SessionStore()

    @router.get("/", response_class=HTMLResponse)
    async def chat_page(request: Request):
        return _TEMPLATES.TemplateResponse(request, "chat.html", {})

    @router.post("/message", response_model=ChatReply)
    async def send_message(body: ChatMessage) -> ChatReply:
        session_id, session = sessions.get_or_create(body.session_id)
        text = body.message.strip()

        if not text:
            return ChatReply(session_id=session_id, reply="Tell me what you'd like to do, e.g. " '"check the balance for member 100234".')

        if is_cancel(text):
            sessions.reset(session_id)
            return ChatReply(session_id=session_id, reply="Okay, starting over.")

        capability_id = session.pending_capability_id or detect_capability(text)
        if capability_id is None:
            return ChatReply(session_id=session_id, reply=f"I didn't recognize that request. {_catalog_help(service)}")

        try:
            artifact = service.catalog.get(capability_id)
        except CapabilityNotFoundError:
            sessions.reset(session_id)
            return ChatReply(session_id=session_id, reply="That capability isn't available right now.")

        required = required_business_inputs(artifact)

        # If exactly one required slot was outstanding when this turn began,
        # this message is the answer to that specific question — accept it
        # verbatim when ordinary pattern extraction finds nothing, rather
        # than asking the same question forever (e.g. a free-text mailing
        # address matches none of nlu.py's regexes).
        awaiting_single_slot: str | None = None
        # member_inquiry's search_mode/search_value pair is asked about
        # together (see nlu.ask_for_missing_inputs); a direct reply like
        # "Lovelace" answers both at once, so it gets the same freeform
        # fallback treatment as a genuinely single outstanding slot.
        awaiting_member_search = False
        if session.pending_capability_id is not None:
            missing_before = [name for name in required if name not in session.collected]
            if len(missing_before) == 1:
                awaiting_single_slot = missing_before[0]
            elif capability_id == "meridian.member_inquiry" and set(missing_before) == {"search_mode", "search_value"}:
                awaiting_member_search = True

        extracted = extract_slots(capability_id, text)
        session.collected.update({name: value for name, value in extracted.items() if value})

        if awaiting_single_slot is not None and awaiting_single_slot not in session.collected:
            session.collected[awaiting_single_slot] = text
        elif awaiting_member_search and "search_mode" not in session.collected:
            guess = extract_member_search_freeform(text)
            if guess is not None:
                session.collected["search_mode"], session.collected["search_value"] = guess

        missing = [name for name in required if name not in session.collected]
        if missing:
            session.pending_capability_id = capability_id
            ask = ask_for_missing_inputs(artifact, missing, session.collected)
            return ChatReply(
                session_id=session_id,
                reply=f'{ask} (Say "cancel" to start over.)',
            )

        inputs = dict(session.collected)
        sessions.reset(session_id)
        try:
            result = await service.invoke(capability_id, inputs)
        except InvalidArgumentsError as exc:
            return ChatReply(session_id=session_id, reply=f"I can't do that: {exc.message}")
        except CapabilityNotFoundError:
            return ChatReply(session_id=session_id, reply="That capability isn't available right now.")

        return ChatReply(session_id=session_id, reply=_explain(result, artifact.name), result=result)

    return router
