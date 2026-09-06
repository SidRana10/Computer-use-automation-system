"""Read-only catalog of MERIDIAN capability artifacts already on disk.

Loads the same JSON files `uicap replay` reads (`discovery.compiler.load_artifact`)
via the same Pydantic model. This module never writes an artifact and never
touches Playwright; it exists purely to answer "what capabilities exist" and
"give me capability X" for the API/chatbot/dashboard layers.
"""

from __future__ import annotations

from pathlib import Path

from ..discovery.compiler import load_artifact
from ..models.artifact import CapabilityArtifact


class CapabilityNotFoundError(LookupError):
    def __init__(self, capability_id: str):
        super().__init__(f"unknown capability_id {capability_id!r}")
        self.capability_id = capability_id


class CapabilityCatalog:
    """Loads every `*.json` capability artifact in a directory, once, at
    construction. A demo-scale catalog (single digits of capabilities) does
    not need hot-reload or a database; restart the process to pick up a newly
    compiled artifact, exactly like the CLI already requires."""

    def __init__(self, artifacts_dir: Path):
        self._dir = Path(artifacts_dir)
        self._by_id: dict[str, CapabilityArtifact] = {}
        self._paths: dict[str, Path] = {}
        self._load()

    def _load(self) -> None:
        if not self._dir.is_dir():
            return
        for path in sorted(self._dir.glob("*.json")):
            artifact = load_artifact(path)
            self._by_id[artifact.capability_id] = artifact
            self._paths[artifact.capability_id] = path

    def list(self) -> list[CapabilityArtifact]:
        return sorted(self._by_id.values(), key=lambda a: a.capability_id)

    def get(self, capability_id: str) -> CapabilityArtifact:
        try:
            return self._by_id[capability_id]
        except KeyError:
            raise CapabilityNotFoundError(capability_id) from None

    def source_path(self, capability_id: str) -> Path:
        return self._paths[capability_id]
