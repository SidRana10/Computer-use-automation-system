"""Small, testable condition vocabulary used for checkpoints, success
verification, and known error-state detection. Deliberately not a generic
expression language."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, model_validator

from .targets import TargetDescriptor


class ConditionKind(StrEnum):
    URL_MATCHES = "url_matches"
    TEXT_PRESENT = "text_present"
    TEXT_ABSENT = "text_absent"
    ELEMENT_PRESENT = "element_present"
    ELEMENT_ABSENT = "element_absent"
    ELEMENT_VALUE_MATCHES = "element_value_matches"


_TARGET_KINDS = {
    ConditionKind.ELEMENT_PRESENT,
    ConditionKind.ELEMENT_ABSENT,
    ConditionKind.ELEMENT_VALUE_MATCHES,
}
_VALUE_KINDS = {
    ConditionKind.URL_MATCHES,
    ConditionKind.TEXT_PRESENT,
    ConditionKind.TEXT_ABSENT,
    ConditionKind.ELEMENT_VALUE_MATCHES,
}


class ConditionSpec(BaseModel):
    kind: ConditionKind
    target: TargetDescriptor | None = None
    value: str | None = None
    timeout_ms: int | None = None

    @model_validator(mode="after")
    def _shape(self) -> "ConditionSpec":
        if self.kind in _TARGET_KINDS and self.target is None:
            raise ValueError(f"condition kind {self.kind} requires a target")
        if self.kind in _VALUE_KINDS and not self.value:
            raise ValueError(f"condition kind {self.kind} requires a value")
        return self


class ConditionResult(BaseModel):
    satisfied: bool
    kind: ConditionKind
    detail: str = ""
