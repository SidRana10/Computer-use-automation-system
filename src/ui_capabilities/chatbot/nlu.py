"""Deterministic, regex/keyword request understanding for the thin chatbot.

No LLM call, no free-form generation, nothing that could itself decide to
click something: this module's only job is "which capability, with which
typed arguments, does this sentence describe" — the same kind of slot-filling
a rule-based form-fill bot has always done, kept intentionally small per the
P7 instruction not to build a sophisticated agent framework. It is exhaustively
unit-testable without any network access, matching the project's existing
preference for deterministic, offline-testable components wherever a task
does not genuinely require a model.

A natural extension (documented as a future improvement, not built here)
is to swap `detect_capability`/`extract_slots` for a structured-output call to
the same Gemini/Anthropic adapters discovery already uses, behind this exact
function signature — the chatbot loop in `router.py` does not care how a
capability_id and slots were produced.
"""

from __future__ import annotations

import re

from ..api.schemas import SERVER_SUPPLIED_INPUTS
from ..models.artifact import CapabilityArtifact

_MEMBER_NUMBER_RE = re.compile(r"\b\d{6}\b")
_SHARE_ID_RE = re.compile(r"\b\d{6}-[A-Za-z0-9]+-\d+\b")
_AMOUNT_RE = re.compile(r"\$\s?(\d+(?:\.\d{1,2})?)|(\d+(?:\.\d{1,2})?)\s*dollars\b", re.IGNORECASE)
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# MERIDIAN's own phone format is 3-4 digits (e.g. "555-1234"); a full 10-digit
# number is also accepted since a caller may reasonably supply either.
_PHONE_RE = re.compile(r"\b\d{3}-\d{3}-\d{4}\b|\b\d{3}[-.\s]?\d{4}\b")
_SHARE_TYPE_RE = re.compile(r"\b(S0001|S0070|MMKT|CERT)\b", re.IGNORECASE)
_REASON_CODE_RE = re.compile(r"\b(FRAUD|LEGAL|DECEASED)\b", re.IGNORECASE)
# Member-inquiry name search: anchored on the literal word "member" (present
# in every supported trigger phrase) rather than on "for"/"named", which
# used to mis-capture the word "member" itself out of phrases like "search
# for member Lovelace". Tried in order: an explicit "(with/by) last name /
# lastname" qualifier first, then a bare "member <name>" fallback.
_MEMBER_LASTNAME_RE = re.compile(
    r"member\s*(?:number|no\.?)?\s*(?:with\s+|by\s+)?(?:last\s*name|lastname)(?:\s+is)?\s+([A-Za-z][A-Za-z'\-]*)",
    re.IGNORECASE,
)
_MEMBER_PLAIN_NAME_RE = re.compile(r"member\s+(?:number\s+)?([A-Za-z][A-Za-z'\-]*)\b", re.IGNORECASE)

# Checked in order, first match wins. Deliberately generous synonyms for the
# two demo-prioritized requests (balance, transfer); the rest get a smaller
# but still workable set.
_INTENT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("meridian.get_member_balances", ("balance", "balances", "how much")),
    ("meridian.funds_transfer", ("transfer", "move money", " move ", "send money")),
    ("meridian.place_hold", ("hold", "freeze")),
    ("meridian.open_share", ("open a share", "open share", "new share", "open a new account", "open account")),
    (
        "meridian.update_member_info",
        ("update", "change email", "change phone", "change address", "update info", "update member", "change member"),
    ),
    ("meridian.member_inquiry", ("look up", "lookup", "find member", "search for", "who is")),
)

CANCEL_WORDS = frozenset({"cancel", "never mind", "nevermind", "start over", "reset"})


def is_cancel(text: str) -> bool:
    return text.strip().lower() in CANCEL_WORDS


def detect_capability(text: str) -> str | None:
    lowered = f" {text.lower()} "
    for capability_id, keywords in _INTENT_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return capability_id
    return None


def extract_slots(capability_id: str, text: str) -> dict[str, str]:
    """Best-effort extraction of the business slots a capability declares.
    Anything not found is simply absent — the chatbot loop asks for it
    explicitly rather than guessing (P7: never invent a missing argument)."""
    found: dict[str, str] = {}
    numbers = _MEMBER_NUMBER_RE.findall(text)
    shares = _SHARE_ID_RE.findall(text)

    if capability_id != "meridian.member_inquiry" and numbers:
        found["member_number"] = numbers[0]

    if capability_id == "meridian.funds_transfer":
        if len(shares) >= 1:
            found["from_share"] = shares[0]
        if len(shares) >= 2:
            found["to_share"] = shares[1]
        amount = _first_amount(text)
        if amount is not None:
            found["amount"] = amount

    elif capability_id == "meridian.place_hold":
        if shares:
            found["share"] = shares[0]
        reason = _REASON_CODE_RE.search(text)
        if reason:
            found["reason_code"] = reason.group(1).upper()

    elif capability_id == "meridian.open_share":
        share_type = _SHARE_TYPE_RE.search(text)
        if share_type:
            found["share_type"] = share_type.group(1).upper()
        amount = _first_amount(text)
        if amount is not None:
            found["initial_deposit"] = amount

    elif capability_id == "meridian.update_member_info":
        email = _EMAIL_RE.search(text)
        if email:
            found["email"] = email.group(0)
        phone = _PHONE_RE.search(text)
        if phone:
            found["phone"] = phone.group(0)

    elif capability_id == "meridian.member_inquiry":
        if numbers:
            found["search_mode"] = "number"
            found["search_value"] = numbers[0]
        else:
            name_match = _MEMBER_LASTNAME_RE.search(text) or _MEMBER_PLAIN_NAME_RE.search(text)
            if name_match:
                found["search_mode"] = "name"
                found["search_value"] = name_match.group(1)

    return found


def extract_member_search_freeform(text: str) -> tuple[str, str] | None:
    """Interpret a direct reply to a pending "member number or last name?"
    question when the user answers without the word "member" at all (e.g.
    just "Lovelace" or "last name Lovelace"). A numeric reply is already
    covered by the ordinary member-number extraction in `extract_slots`
    (it does not require the word "member" either); this only fills the
    remaining gap — a bare last name with no anchor word to key off."""
    stripped = text.strip()
    match = re.search(
        r"(?:last\s*name|lastname)(?:\s+is)?\s*[:\-]?\s*([A-Za-z][A-Za-z'\-]*)", stripped, re.IGNORECASE
    )
    if match:
        return "name", match.group(1)
    if re.fullmatch(r"[A-Za-z][A-Za-z'\-]*", stripped):
        return "name", stripped
    return None


def _first_amount(text: str) -> str | None:
    match = _AMOUNT_RE.search(text)
    if not match:
        return None
    return match.group(1) or match.group(2)


def required_business_inputs(artifact: CapabilityArtifact) -> list[str]:
    """Required inputs a caller must supply — the artifact's own contract is
    the source of truth, never a hardcoded list, so this never drifts from
    what `binder.validate_and_bind` will actually enforce."""
    return [
        spec.name
        for spec in artifact.contract.inputs
        if spec.required and spec.name not in SERVER_SUPPLIED_INPUTS
    ]


def input_description(artifact: CapabilityArtifact, name: str) -> str:
    for spec in artifact.contract.inputs:
        if spec.name == name:
            return spec.description
    return name


# Natural-language prompts for the business-facing required inputs on the 7
# MERIDIAN capabilities (`targets/meridian.py::MERIDIAN_INPUT_SPECS`) — a
# small, static lookup, not a dialogue framework. A caller never needs to
# know internal field names like `from_share`/`search_mode`; this is only
# ever used to phrase a question, never to change what the artifact contract
# actually requires. `search_mode`/`search_value` are handled specially in
# `ask_for_missing_inputs` because their meaning depends on each other.
_FIELD_QUESTIONS: dict[str, str] = {
    "member_number": "What member number should I use?",
    "from_share": "Which share should the transfer be from?",
    "to_share": "Which share should the transfer go to?",
    "amount": "How much should I transfer?",
    "share_type": "What type of share should I open (S0001, S0070, MMKT, or CERT)?",
    "initial_deposit": "What should the initial deposit be?",
    "email": "What email address should I use?",
    "phone": "What phone number should I use?",
    "address": "What should the new mailing address be?",
    "share": "Which share should the hold be placed on?",
    "reason_code": "What's the reason for the hold (FRAUD, LEGAL, or DECEASED)?",
}


def ask_for_missing_inputs(artifact: CapabilityArtifact, missing: list[str], collected: dict[str, str]) -> str:
    """A short, conversational question for the still-missing required
    inputs — never the raw field name, and never a guess at the value.

    `member_inquiry`'s `search_mode`/`search_value` pair is special-cased:
    asking about them separately ("I need search_mode. I need
    search_value.") would be exactly the internal-field-name leakage this
    exists to avoid, so the two are folded into one question, or answered
    with whichever half is still actually missing once the other is known.
    """
    missing_set = set(missing)
    if {"search_mode", "search_value"} <= missing_set:
        return "Would you like to search by member number or last name — and what's the value?"
    if "search_value" in missing_set:
        mode = collected.get("search_mode")
        if mode == "name":
            return "What last name should I search for?"
        if mode == "number":
            return "What member number should I use?"
    if "search_mode" in missing_set:
        return "Would you like to search by member number or last name?"
    questions = [
        _FIELD_QUESTIONS.get(name) or f"What {input_description(artifact, name)} should I use?" for name in missing
    ]
    return " ".join(questions)
