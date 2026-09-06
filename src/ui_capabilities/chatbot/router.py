"""Thin chatbot: understand -> pick a capability -> fill typed args -> call
`CapabilityService.invoke` -> explain the structured result in plain
language.

This module never imports a surface, the replay engine, or Playwright — it
only ever calls the same `CapabilityService` the HTTP capability API uses
(`api/service.py`), so there is exactly one invocation path in the process,
not a chatbot-shaped shortcut around it.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..api.catalog import CapabilityNotFoundError
from ..api.service import CapabilityService, InvalidArgumentsError
from ..models.results import BusinessOutcomeResult, EscalatedResult, FailureResult, RunResult, SuccessResult
from .nlu import detect_capability, extract_slots, input_description, is_cancel, required_business_inputs
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
    """A list-shaped output (e.g. a member's full share table) is a lot of
    text for a chat reply; summarize it by count and point the reader at the
    dashboard for the full structured detail rather than dumping every row."""
    if isinstance(value, list):
        return f"{len(value)} result(s) — see the run's dashboard page for the full table"
    return str(value)


def _explain(result: RunResult, capability_name: str) -> str:
    if isinstance(result, SuccessResult):
        if result.outputs:
            details = "; ".join(f"{k} = {_format_output(v)}" for k, v in result.outputs.items())
            return f"Done. {capability_name} succeeded — {details}. (run {result.run_id})"
        return f"Done. {capability_name} succeeded. (run {result.run_id})"
    if isinstance(result, BusinessOutcomeResult):
        return f"{capability_name} did not go through: {result.message} [{result.code}]. (run {result.run_id})"
    if isinstance(result, EscalatedResult):
        return (
            f"{capability_name} needs a human: {result.message} [{result.code}]. "
            f"Resolve intervention {result.intervention_id} in the operator console, "
            f"then check run {result.run_id} in the dashboard for the outcome."
        )
    if isinstance(result, FailureResult):
        return f"{capability_name} failed: {result.observed or result.code} [{result.code}]. (run {result.run_id})"
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
        if session.pending_capability_id is not None:
            missing_before = [name for name in required if name not in session.collected]
            if len(missing_before) == 1:
                awaiting_single_slot = missing_before[0]

        extracted = extract_slots(capability_id, text)
        session.collected.update({name: value for name, value in extracted.items() if value})

        if awaiting_single_slot is not None and awaiting_single_slot not in session.collected:
            session.collected[awaiting_single_slot] = text

        missing = [name for name in required if name not in session.collected]
        if missing:
            session.pending_capability_id = capability_id
            asks = "; ".join(f"{name} ({input_description(artifact, name)})" for name in missing)
            return ChatReply(
                session_id=session_id,
                reply=f"To do that ({artifact.name}) I still need: {asks}. Say \"cancel\" to start over.",
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
