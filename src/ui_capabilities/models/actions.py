"""Strict structured action contract for LLM discovery.

The model chooses exactly one of these per turn. There is deliberately no
shell/JS/code action: the model proposes a narrow UI action; application code
owns policy, resolution, execution, and recording.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, model_validator

ELEMENT_REF_PATTERN = r"^e\d+$"


class ValueSource(BaseModel):
    """Where a fill/select value comes from: a declared invocation input
    (bound by the executor, so the model never needs the sensitive value) or a
    safe literal the model read from the UI/goal."""

    input_name: str | None = None
    literal: str | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "ValueSource":
        if bool(self.input_name) == bool(self.literal is not None):
            raise ValueError("exactly one of input_name or literal must be provided")
        return self


class NavigateAction(BaseModel):
    action: Literal["navigate"] = "navigate"
    url: str
    rationale_summary: str = ""


class ClickAction(BaseModel):
    action: Literal["click"] = "click"
    element_ref: str | None = Field(default=None, pattern=ELEMENT_REF_PATTERN)
    # Discovery-only fallback when no semantic element exists. Never replay identity.
    coordinate: tuple[float, float] | None = None
    rationale_summary: str = ""

    @model_validator(mode="after")
    def _has_target(self) -> "ClickAction":
        if self.element_ref is None and self.coordinate is None:
            raise ValueError("click requires element_ref or coordinate")
        return self


class FillAction(BaseModel):
    action: Literal["fill"] = "fill"
    element_ref: str = Field(pattern=ELEMENT_REF_PATTERN)
    value_source: ValueSource
    rationale_summary: str = ""


class SelectAction(BaseModel):
    action: Literal["select"] = "select"
    element_ref: str = Field(pattern=ELEMENT_REF_PATTERN)
    value_source: ValueSource
    rationale_summary: str = ""


class ExtractAction(BaseModel):
    action: Literal["extract"] = "extract"
    element_ref: str = Field(pattern=ELEMENT_REF_PATTERN)
    output_name: str
    output_type: Literal["string", "integer", "decimal", "boolean"] = "string"
    rationale_summary: str = ""


class WaitAction(BaseModel):
    action: Literal["wait"] = "wait"
    milliseconds: int = Field(gt=0)
    rationale_summary: str = ""


class SuggestedCondition(BaseModel):
    kind: Literal["url_matches", "text_present"]
    value: str


class DoneAction(BaseModel):
    action: Literal["done"] = "done"
    success_summary: str
    suggested_success_condition: SuggestedCondition | None = None


class RequestHumanAction(BaseModel):
    action: Literal["request_human"] = "request_human"
    reason_code: Literal["blocked", "ambiguous", "risky_action", "unexpected_state", "other"] = "other"
    message: str


DiscoveryAction = Annotated[
    Union[
        NavigateAction,
        ClickAction,
        FillAction,
        SelectAction,
        ExtractAction,
        WaitAction,
        DoneAction,
        RequestHumanAction,
    ],
    Field(discriminator="action"),
]
