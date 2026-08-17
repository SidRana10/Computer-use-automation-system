"""Known runtime-condition detectors per target app family.

Compiling error rules is deterministic application knowledge, not model
output: for a given app family we know what "not found", the idle
interstitial, or session expiry look like. In the multi-tenant design this is
exactly the kind of vendor-family knowledge a base capability would carry,
with per-tenant overrides.
"""

from __future__ import annotations

from ..models.artifact import ErrorRule, RecoveryActionSpec
from ..models.conditions import ConditionKind, ConditionSpec
from ..models.errors import ErrorClassification
from ..models.targets import LocatorKind, LocatorStrategy, TargetDescriptor

_DETECT_TIMEOUT_MS = 400  # rule detectors must be fast; they run on failures


def demo_app_error_rules() -> list[ErrorRule]:
    return [
        ErrorRule(
            code="MEMBER_NOT_FOUND",
            classification=ErrorClassification.BUSINESS_OUTCOME,
            when=[
                ConditionSpec(
                    kind=ConditionKind.TEXT_PRESENT,
                    value="No member was found for that identifier.",
                    timeout_ms=_DETECT_TIMEOUT_MS,
                )
            ],
            caller_message="No member matched the supplied identifier.",
        ),
        ErrorRule(
            code="VALIDATION_REJECTED",
            classification=ErrorClassification.BUSINESS_OUTCOME,
            when=[
                ConditionSpec(
                    kind=ConditionKind.TEXT_PRESENT,
                    value="Member ID must match M-#####.",
                    timeout_ms=_DETECT_TIMEOUT_MS,
                )
            ],
            caller_message="The supplied member identifier failed validation.",
        ),
        ErrorRule(
            code="PERMISSION_DENIED",
            classification=ErrorClassification.BUSINESS_OUTCOME,
            when=[
                ConditionSpec(
                    kind=ConditionKind.TEXT_PRESENT,
                    value="You do not have permission",
                    timeout_ms=_DETECT_TIMEOUT_MS,
                )
            ],
            caller_message="The operator role is not permitted to perform this action for this member.",
        ),
        ErrorRule(
            code="KNOWN_INTERSTITIAL",
            classification=ErrorClassification.RECOVERABLE,
            when=[
                ConditionSpec(
                    kind=ConditionKind.TEXT_PRESENT,
                    value="Your session has been idle. Continue session?",
                    timeout_ms=_DETECT_TIMEOUT_MS,
                )
            ],
            recovery=[
                RecoveryActionSpec(
                    kind="dismiss",
                    target=TargetDescriptor(
                        description="Continue-session button on idle interstitial",
                        strategies=[
                            LocatorStrategy(kind=LocatorKind.ROLE_NAME, role="button", name="Continue"),
                            LocatorStrategy(kind=LocatorKind.TEXT, value="Continue"),
                        ],
                    ),
                )
            ],
            max_attempts=2,
            caller_message="Known idle-session interstitial was dismissed.",
        ),
        ErrorRule(
            code="TRANSIENT_LOAD",
            classification=ErrorClassification.RECOVERABLE,
            when=[
                ConditionSpec(
                    kind=ConditionKind.TEXT_PRESENT,
                    value="Accounts are loading.",
                    timeout_ms=_DETECT_TIMEOUT_MS,
                )
            ],
            recovery=[
                RecoveryActionSpec(kind="wait", wait_ms=1200),
                RecoveryActionSpec(kind="reload"),
            ],
            max_attempts=2,
            caller_message="Transient load state; waited, refreshed, and retried.",
        ),
        ErrorRule(
            code="SESSION_EXPIRED",
            classification=ErrorClassification.HARD_FAILURE,
            when=[
                ConditionSpec(
                    kind=ConditionKind.TEXT_PRESENT,
                    value="Your session has expired.",
                    timeout_ms=_DETECT_TIMEOUT_MS,
                )
            ],
            caller_message="The console session expired; no credential-free recovery exists, so this run stops.",
        ),
    ]
