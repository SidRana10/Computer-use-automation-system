"""Error taxonomy: expected business outcomes vs recoverable runtime
conditions vs hard failures. Replay must respond deliberately, never blindly."""

from __future__ import annotations

from enum import StrEnum


class RiskLevel(StrEnum):
    SAFE = "safe"
    REVERSIBLE = "reversible"
    RISKY = "risky"
    IRREVERSIBLE = "irreversible"


_RISK_ORDER = {
    RiskLevel.SAFE: 0,
    RiskLevel.REVERSIBLE: 1,
    RiskLevel.RISKY: 2,
    RiskLevel.IRREVERSIBLE: 3,
}


def risk_exceeds(risk: RiskLevel, ceiling: RiskLevel) -> bool:
    return _RISK_ORDER[risk] > _RISK_ORDER[ceiling]


def stricter_risk(a: RiskLevel, b: RiskLevel) -> RiskLevel:
    """Lower ceiling wins when composing policies."""
    return a if _RISK_ORDER[a] <= _RISK_ORDER[b] else b


class ErrorClassification(StrEnum):
    BUSINESS_OUTCOME = "business_outcome"
    RECOVERABLE = "recoverable"
    HARD_FAILURE = "hard_failure"


class BusinessOutcomeCode(StrEnum):
    MEMBER_NOT_FOUND = "MEMBER_NOT_FOUND"
    VALIDATION_REJECTED = "VALIDATION_REJECTED"
    PERMISSION_DENIED = "PERMISSION_DENIED"


class RecoverableCode(StrEnum):
    KNOWN_INTERSTITIAL = "KNOWN_INTERSTITIAL"
    TRANSIENT_LOAD = "TRANSIENT_LOAD"
    TEMPORARY_APP_ERROR = "TEMPORARY_APP_ERROR"


class FailureCode(StrEnum):
    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    AMBIGUOUS_TARGET = "AMBIGUOUS_TARGET"
    CHECKPOINT_FAILED = "CHECKPOINT_FAILED"
    UNEXPECTED_STATE = "UNEXPECTED_STATE"
    OUTPUT_EXTRACTION_FAILED = "OUTPUT_EXTRACTION_FAILED"
    TARGET_APP_MISMATCH = "TARGET_APP_MISMATCH"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    RETRY_EXHAUSTED = "RETRY_EXHAUSTED"
    INVOCATION_INVALID = "INVOCATION_INVALID"
    ARTIFACT_INVALID = "ARTIFACT_INVALID"
    EXECUTION_ERROR = "EXECUTION_ERROR"


class CapabilityError(Exception):
    """Base for structured internal errors."""


class CompileError(CapabilityError):
    """Raised when a successful run cannot be compiled into a valid,
    parameterized, PII-free artifact. The compiler fails loudly rather than
    emitting a broken capability."""
