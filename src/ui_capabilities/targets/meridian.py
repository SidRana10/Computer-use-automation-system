"""MERIDIAN CORE target profile.

Every string below was verified against the live application during Phase-2
reconnaissance; each error rule cites the observed page it detects.

Two properties of this target drove core work elsewhere:

* it renders no `id`, `aria-label`, `data-*` or `<label>` attributes at all, so
  control identity comes from form `name` attributes, submit-button `value`
  captions, and link text;
* it is served over HTTPS, which exposed a policy bug where a URL without an
  explicit port was assumed to be port 80.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from ..models.artifact import ErrorRule, InputSpec, RecoveryActionSpec
from ..models.conditions import ConditionKind, ConditionSpec
from ..models.errors import ErrorClassification, RiskLevel
from ..policy.config import PolicyConfig, default_port_for
from .registry import TargetProfile

DEFAULT_ENTRY_POINT = "https://web-sample.interface-hiring.com"

# Detectors run on the failure path and must be fast.
_DETECT_TIMEOUT_MS = 400

# Codes a capability may declare as human-owned in its own policy block. Naming
# them here documents the contract; whether a given capability escalates is
# decided per artifact, never globally.
SUPERVISOR_REQUIRED = "SUPERVISOR_REQUIRED"


def meridian_error_rules() -> list[ErrorRule]:
    """Known MERIDIAN runtime conditions, most specific first.

    Classification answers "what happened" only. Routing a condition to a human
    is a separate, per-capability policy decision (`escalate_on_codes`).
    """

    def when_text(value: str) -> list[ConditionSpec]:
        return [ConditionSpec(kind=ConditionKind.TEXT_PRESENT, value=value, timeout_ms=_DETECT_TIMEOUT_MS)]

    return [
        ErrorRule(
            code="BAD_LOGIN",
            classification=ErrorClassification.BUSINESS_OUTCOME,
            when=when_text("Invalid operator ID or password."),
            caller_message="The supplied operator credentials were rejected by MERIDIAN.",
        ),
        ErrorRule(
            code=SUPERVISOR_REQUIRED,
            classification=ErrorClassification.HARD_FAILURE,
            when=when_text("is not authorized to perform this function"),
            caller_message=(
                "MERIDIAN requires a supervisor profile for this function; the signed-on operator "
                "is not authorized and automation will not attempt to bypass it."
            ),
        ),
        ErrorRule(
            code="SESSION_EXPIRED",
            classification=ErrorClassification.HARD_FAILURE,
            when=when_text("your session ended due to inactivity"),
            caller_message=(
                "The MERIDIAN session ended; re-authentication is required, so this run stops "
                "rather than resuming a flow whose state is unknown."
            ),
        ),
        ErrorRule(
            code="MEMBER_NOT_FOUND",
            classification=ErrorClassification.BUSINESS_OUTCOME,
            when=when_text("The requested member record could not be located on this host."),
            caller_message="No MERIDIAN member record exists for that member number.",
        ),
        ErrorRule(
            code="NO_SEARCH_RESULTS",
            classification=ErrorClassification.BUSINESS_OUTCOME,
            when=when_text("No member records matched your search."),
            caller_message="The member inquiry returned no matching records.",
        ),
        ErrorRule(
            code="TRANSACTION_REJECTED",
            classification=ErrorClassification.BUSINESS_OUTCOME,
            when=when_text("The transaction could not be validated:"),
            caller_message=(
                "MERIDIAN rejected the transaction during validation "
                "(for example insufficient available balance in the source share)."
            ),
        ),
        ErrorRule(
            code="FIELD_VALIDATION_FAILED",
            classification=ErrorClassification.BUSINESS_OUTCOME,
            when=when_text("Please correct the following:"),
            caller_message="One or more submitted field values were rejected by MERIDIAN validation.",
        ),
        ErrorRule(
            code="VALIDATION_REJECTED",
            classification=ErrorClassification.BUSINESS_OUTCOME,
            when=when_text("The transaction could not be completed as entered."),
            caller_message="MERIDIAN rejected the transaction as entered.",
        ),
        ErrorRule(
            code="MAINTENANCE_WINDOW",
            classification=ErrorClassification.RECOVERABLE,
            when=when_text("The host is temporarily unavailable"),
            # The page's own "Continue" control leaves the flow (it goes to the
            # main menu), so the bounded recovery is wait-and-reload in place.
            recovery=[
                RecoveryActionSpec(kind="wait", wait_ms=1500),
                RecoveryActionSpec(kind="reload"),
            ],
            max_attempts=2,
            caller_message="MERIDIAN reported a maintenance window; waited and retried within budget.",
        ),
        ErrorRule(
            code="APPLICATION_ERROR",
            classification=ErrorClassification.HARD_FAILURE,
            when=when_text("An unexpected error occurred while processing your request."),
            caller_message="MERIDIAN returned an application error; the run stopped and preserved evidence.",
        ),
    ]


def meridian_policy(target_base_url: str = DEFAULT_ENTRY_POINT) -> PolicyConfig:
    """Allowlist for MERIDIAN.

    `/settings` is deliberately excluded: it is the fault-injection console and
    is operator tooling, not part of the automated surface — the same line the
    Northstar profile draws around `/demo/**`.
    """
    parsed = urlparse(target_base_url)
    return PolicyConfig(
        allowed_domains=[parsed.hostname or "web-sample.interface-hiring.com"],
        allowed_ports=[default_port_for(target_base_url)],
        allowed_route_patterns=["/", "/signon", "/signoff", "/menu", "/members", "/members/**"],
        allowed_actions=["navigate", "click", "fill", "select", "extract", "wait_for", "assert", "wait"],
        max_unattended_risk=RiskLevel.REVERSIBLE,
        require_human_for=[RiskLevel.RISKY, RiskLevel.IRREVERSIBLE],
        # Control captions observed on the live target. Classification is by
        # visible identity, decided by policy code rather than by a model.
        irreversible_control_patterns=["apply hold", "post transfer"],
        risky_control_patterns=["save changes"],
    )


MERIDIAN_INPUT_SPECS: dict[str, InputSpec] = {
    "operator_id": InputSpec(
        name="operator_id",
        type="string",
        sensitive=True,
        credential=True,
        description="MERIDIAN operator sign-on ID (supplied by the environment, never by a caller)",
    ),
    "password": InputSpec(
        name="password",
        type="string",
        sensitive=True,
        credential=True,
        description="MERIDIAN operator password (supplied by the environment, never by a caller)",
    ),
    "branch": InputSpec(
        name="branch",
        type="string",
        description="Branch code selected at sign-on, e.g. MAIN-001",
    ),
    "member_number": InputSpec(
        name="member_number",
        type="string",
        sensitive=True,
        pattern=r"\d{6}",
        description="Six-digit MERIDIAN member number",
    ),
}

# Regions painted over in durable screenshots. The status bar carries the
# operator id and live session id; the member detail rows carry contact
# details; the third column of the data table carries balances.
#
# These are expressed with the existing CSS strategy, which Playwright's engine
# resolves including `:text-is()`; no new locator kind was needed.
#
# They are anchored on the label cell's text and take the adjacent cell, rather
# than indexing into the row: this target packs several label/value pairs into
# one `<tr>`, so `tr:has(...) > td:nth-child(2)` silently selected the wrong
# cell (it returned the member number for the "Name:" anchor). Verified live.
SCREENSHOT_MASK_SELECTORS: tuple[str, ...] = (
    'td[bgcolor="#e4e4e4"]',
    'td.lbl:text-is("Member No.:") + td',
    'td.lbl:text-is("Name:") + td',
    'td.lbl:text-is("E-mail:") + td',
    'td.lbl:text-is("Phone:") + td',
    'td.lbl:text-is("Address:") + td',
    # Transaction screens repeat the member identity in a plain <font> banner
    # rather than a labelled row, and the menu names the signed-on operator.
    # Matched on content so static help text is not masked pointlessly.
    'font:text-matches("Member [0-9]+ - ")',
    'font:has-text("Signed on as")',
    # The sign-on screen prints a demo-credentials hint naming other
    # operators. Only the operator this run bound is a registered runtime
    # value, so the rest would otherwise survive into evidence.
    'font:has-text("Demo operators")',
    # A <select> paints its chosen option itself, so the share id and balance
    # in the caption are only removable by masking the control.
    'select[name="from"]',
    'select[name="to"]',
    'select[name="share"]',
    # Sign-on credential fields. Found by audit: the discovery loop screenshots
    # before/after every action, so a mid-fill screenshot shows whatever has
    # been typed so far. The password field is browser-masked by its own
    # type="password" rendering, but the operator id is a plain text field and
    # was captured in clear text ("teller1") in a genuine discovery run.
    'input[name="operator"]',
    'input[name="password"]',
    # Transaction review/confirmation rows. Durable images prove which screen
    # and which step; the structured run result carries the actual values back
    # to the caller.
    'td.lbl:text-is("Member:") + td',
    'td.lbl:text-is("From:") + td',
    'td.lbl:text-is("To:") + td',
    'td.lbl:text-is("Amount:") + td',
    'td.lbl:text-is("Share:") + td',
    'td.lbl:text-is("Confirmation:") + td',
    # The two genuinely positional selectors: a table column cannot be
    # content-anchored in CSS. Scoped away from the header row and documented
    # here as a deliberate last resort. Column 1 is the share/member identifier
    # (share ids embed the member number, which the DOM path already scrubs, so
    # leaving it legible in an image would be an inconsistent control) and
    # column 3 is the balance. Type, status and row count stay visible, which is
    # what makes the image useful as proof the right screen was reached.
    'table[border="1"] > tbody > tr:not(.lbl) > td:nth-child(1)',
    'table[border="1"] > tbody > tr:not(.lbl) > td:nth-child(3)',
)

# Applied by the central Redactor to every durable text/DOM write. Registered
# runtime values alone are not sufficient here: the page renders a live session
# id, a per-session transaction token, and contact details the run never
# supplied or extracted.
REDACTION_TEXT_PATTERNS: tuple[str, ...] = (
    # Live session identifier, printed in the status bar of every page.
    r"SID\s+[A-F0-9]{6,}",
    # Signed-on operator, printed uppercase in the status bar. Registering the
    # bound input value does not cover it: the page renders a different case
    # from the value the caller supplied.
    r"OPR\s+[A-Z0-9]+",
    # Per-session transaction token, present in every write form's hidden field.
    r'(name="_token"\s+value=")[^"]*',
    r"(SESSION_TOKEN=)[A-Za-z0-9\-]+",
    # Member contact details rendered on record and update screens.
    r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
    r"\b\d{3}-\d{4}\b",
    # Any rendered currency amount. Only the value a caller explicitly requested
    # is returned to them by the API; balances must not accumulate in evidence.
    r"\$\d[\d,]*\.\d{2}",
)

MERIDIAN_PROFILE = TargetProfile(
    app_id="meridian_core",
    vendor_family="cornerstone_meridian",
    display_name="MERIDIAN CORE — Member Services Platform (Cornerstone Financial Systems)",
    default_entry_point=DEFAULT_ENTRY_POINT,
    policy_factory=meridian_policy,
    error_rules_factory=meridian_error_rules,
    input_specs=MERIDIAN_INPUT_SPECS,
    heading_selector="h1",
    title_marker="Meridian Core",
    version_pattern=re.compile(r"Member Services Platform\s+v([\w.\-]+)"),
    screenshot_mask_selectors=SCREENSHOT_MASK_SELECTORS,
    redaction_text_patterns=REDACTION_TEXT_PATTERNS,
    credential_inputs=("operator_id", "password"),
    # Verified during the P1 audit: a MERIDIAN trace.zip contained the sign-on
    # POST body verbatim (`operator=...&password=...`), the fill action
    # parameters, unmasked frame screenshots and raw DOM. Masking and
    # redaction operate on the evidence the surface writes, not on the
    # trace recorder, so tracing is off for this target. Redacted logs,
    # masked screenshots, redacted DOM snapshots, timings and the structured
    # result remain.
    durable_traces=False,
)
