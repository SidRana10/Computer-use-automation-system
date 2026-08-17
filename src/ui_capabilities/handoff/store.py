"""In-memory intervention store with asyncio wakeups and a redacted JSON dump
for evidence. A single local run is in scope; a production version would sit
behind a durable store with session leases."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from ..models.intervention import InterventionRequest


class InterventionStore:
    def __init__(self, dump_path: Path | None = None):
        self._items: dict[str, InterventionRequest] = {}
        self._events: dict[str, asyncio.Event] = {}
        self._dump_path = dump_path

    def add(self, intervention: InterventionRequest) -> None:
        self._items[intervention.intervention_id] = intervention
        self._events[intervention.intervention_id] = asyncio.Event()
        self._dump()

    def get(self, intervention_id: str) -> InterventionRequest:
        if intervention_id not in self._items:
            raise KeyError(f"unknown intervention {intervention_id!r}")
        return self._items[intervention_id]

    def all(self) -> list[InterventionRequest]:
        return sorted(self._items.values(), key=lambda i: i.created_at, reverse=True)

    def update(self, intervention: InterventionRequest) -> None:
        self._items[intervention.intervention_id] = intervention
        self._dump()

    def signal(self, intervention_id: str) -> None:
        self._events[intervention_id].set()

    async def wait(self, intervention_id: str) -> None:
        await self._events[intervention_id].wait()

    def _dump(self) -> None:
        if self._dump_path is None:
            return
        self._dump_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [json.loads(i.model_dump_json()) for i in self.all()]
        self._dump_path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
