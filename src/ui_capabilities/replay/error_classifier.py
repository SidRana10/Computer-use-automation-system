"""Classify a failed step against the artifact's declared error rules.

Rules are evaluated in artifact order; the first rule whose conditions all
hold wins. No rule matching means an unclassified hard failure.
"""

from __future__ import annotations

from ..models.artifact import CapabilityArtifact, ErrorRule
from ..surfaces.base import SurfaceAdapter


async def classify_current_state(surface: SurfaceAdapter, artifact: CapabilityArtifact) -> ErrorRule | None:
    for rule in artifact.error_rules:
        all_hold = True
        for condition in rule.when:
            result = await surface.evaluate_condition(condition)
            if not result.satisfied:
                all_hold = False
                break
        if all_hold:
            return rule
    return None
