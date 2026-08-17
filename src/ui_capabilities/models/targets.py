"""Target identification: ordered locator strategy chains.

A TargetDescriptor says *what control is intended*; strategies are ordered
from most to least robust. Coordinates are deliberately absent: they are a
discovery-time hint only and never a normal replay identity.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class LocatorKind(StrEnum):
    ROLE_NAME = "role_name"
    LABEL = "label"
    PLACEHOLDER = "placeholder"
    TEXT = "text"
    STABLE_ATTRIBUTE = "stable_attribute"
    CSS = "css"
    FRAME_PATH = "frame_path"


# Replay preference order (docs/03): semantic first, CSS last-resort.
LOCATOR_PRIORITY: dict[LocatorKind, int] = {
    LocatorKind.ROLE_NAME: 0,
    LocatorKind.LABEL: 1,
    LocatorKind.PLACEHOLDER: 2,
    LocatorKind.TEXT: 3,
    LocatorKind.STABLE_ATTRIBUTE: 4,
    LocatorKind.CSS: 5,
    LocatorKind.FRAME_PATH: 6,
}


class LocatorStrategy(BaseModel):
    kind: LocatorKind
    role: str | None = None
    name: str | None = None
    value: str | None = None
    attribute: str | None = None
    exact: bool = True
    confidence: float | None = None

    @field_validator("confidence")
    @classmethod
    def _confidence_range(cls, v: float | None) -> float | None:
        if v is not None and not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        return v


class TargetDescriptor(BaseModel):
    description: str
    strategies: list[LocatorStrategy] = Field(min_length=1)

    def ordered_strategies(self) -> list[LocatorStrategy]:
        """Strategies in stored order; storage order is authoritative, this is
        a stable-sorted safety net against unordered hand-authored artifacts."""
        return sorted(self.strategies, key=lambda s: LOCATOR_PRIORITY[s.kind])
