"""Northstar Credit Union — Member Servicing Console (Demo).

An intentionally plain, server-rendered, legacy-styled synthetic target app.
Fictional data only. Exceptional states are deterministic knobs (see state.py).
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .data import MEMBER_ID_PATTERN
from .state import STATE, PendingSubAccount

app = FastAPI(title="Northstar Credit Union — Member Servicing Console (Demo)", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def _render(request: Request, template: str, **ctx) -> HTMLResponse:
    return templates.TemplateResponse(request, template, ctx)


def _session_guard(request: Request) -> HTMLResponse | None:
    if STATE.session_expired:
        return _render(request, "session_expired.html")
    return None


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return _render(request, "dashboard.html", member_count=len(STATE.members))


@app.get("/members/search", response_class=HTMLResponse)
async def member_search(request: Request, member_id: str | None = None):
    if expired := _session_guard(request):
        return expired
    error = None
    if member_id is not None:
        member_id = member_id.strip()
        if not re.match(MEMBER_ID_PATTERN, member_id):
            error = "Member ID must match M-#####."
        elif member_id in STATE.members:
            return RedirectResponse(url=f"/members/{member_id}", status_code=303)
        else:
            error = "No member was found for that identifier."
    return _render(request, "search.html", error=error, searched=member_id)


@app.get("/members/{member_id}", response_class=HTMLResponse)
async def member_summary(request: Request, member_id: str):
    if expired := _session_guard(request):
        return expired
    member = STATE.members.get(member_id)
    if member is None:
        return _render(request, "search.html", error="No member was found for that identifier.", searched=member_id)
    return _render(
        request,
        "member.html",
        member=member,
        missing_accounts_control=(STATE.failure_mode == "missing_accounts_control"),
    )


@app.get("/members/{member_id}/accounts", response_class=HTMLResponse)
async def member_accounts(request: Request, member_id: str):
    if expired := _session_guard(request):
        return expired
    member = STATE.members.get(member_id)
    if member is None:
        return _render(request, "search.html", error="No member was found for that identifier.", searched=member_id)
    if STATE.interstitial_pending:
        return _render(request, "interstitial.html", next_url=f"/members/{member_id}/accounts")
    if STATE.slow_accounts_pending:
        STATE.slow_accounts_pending = False
        await asyncio.sleep(0.4)
        return _render(request, "transient.html", refresh_url=f"/members/{member_id}/accounts")
    return _render(request, "accounts.html", member=member)


@app.post("/session/continue", response_class=HTMLResponse)
async def session_continue(request: Request, next_url: str = Form(alias="next")):
    STATE.interstitial_pending = False
    # only ever redirect back into the app
    if not next_url.startswith("/"):
        next_url = "/"
    return RedirectResponse(url=next_url, status_code=303)


# ---------------------------------------------------------------- sub-accounts


@app.get("/members/{member_id}/subaccounts/new", response_class=HTMLResponse)
async def subaccount_new(request: Request, member_id: str):
    if expired := _session_guard(request):
        return expired
    member = STATE.members.get(member_id)
    if member is None:
        return _render(request, "search.html", error="No member was found for that identifier.", searched=member_id)
    if member.denies_subaccounts:
        return _render(request, "permission_denied.html", member=member)
    return _render(request, "subaccount_new.html", member=member)


@app.post("/members/{member_id}/subaccounts/review", response_class=HTMLResponse)
async def subaccount_review(
    request: Request,
    member_id: str,
    account_type: str = Form(...),
    nickname: str = Form(""),
):
    if expired := _session_guard(request):
        return expired
    member = STATE.members.get(member_id)
    if member is None:
        return _render(request, "search.html", error="No member was found for that identifier.", searched=member_id)
    if member.denies_subaccounts:
        return _render(request, "permission_denied.html", member=member)
    STATE.pending_subaccounts[member_id] = PendingSubAccount(account_type=account_type, nickname=nickname.strip())
    return _render(request, "subaccount_review.html", member=member, pending=STATE.pending_subaccounts[member_id])


@app.post("/members/{member_id}/subaccounts/confirm", response_class=HTMLResponse)
async def subaccount_confirm(request: Request, member_id: str):
    if expired := _session_guard(request):
        return expired
    member = STATE.members.get(member_id)
    pending = STATE.pending_subaccounts.pop(member_id, None)
    if member is None or pending is None:
        return RedirectResponse(url=f"/members/{member_id}/subaccounts/new", status_code=303)
    confirmation = STATE.next_confirmation_number()
    from .data import Account

    member.accounts.append(Account(pending.account_type, f"sub{STATE.confirmation_seq}", 0.00))
    request.app.state.last_confirmation = confirmation
    return RedirectResponse(url=f"/members/{member_id}/subaccounts/confirmed?ref={confirmation}", status_code=303)


@app.get("/members/{member_id}/subaccounts/confirmed", response_class=HTMLResponse)
async def subaccount_confirmed(request: Request, member_id: str, ref: str = ""):
    if expired := _session_guard(request):
        return expired
    member = STATE.members.get(member_id)
    if member is None:
        return _render(request, "search.html", error="No member was found for that identifier.", searched=member_id)
    return _render(request, "subaccount_confirmed.html", member=member, confirmation=ref or "SUB-00000")


# ------------------------------------------------------------- demo tooling
# Local-only test/demo knobs. These endpoints are NOT part of the automated
# surface: the automation policy allowlist does not include /demo/**.


@app.post("/demo/config")
async def demo_config(
    interstitial: bool | None = None,
    slow_accounts: bool | None = None,
    failure: str | None = None,
    session_expired: bool | None = None,
):
    if interstitial is not None:
        STATE.interstitial_pending = interstitial
    if slow_accounts is not None:
        STATE.slow_accounts_pending = slow_accounts
    if failure is not None:
        STATE.failure_mode = None if failure in ("", "none") else failure
    if session_expired is not None:
        STATE.session_expired = session_expired
    return {
        "interstitial_pending": STATE.interstitial_pending,
        "slow_accounts_pending": STATE.slow_accounts_pending,
        "failure_mode": STATE.failure_mode,
        "session_expired": STATE.session_expired,
    }


@app.post("/demo/reset")
async def demo_reset():
    STATE.reset()
    return {"reset": True}
