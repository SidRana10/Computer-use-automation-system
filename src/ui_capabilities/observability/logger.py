"""Structured JSONL run logger. Every event passes through the central
Redactor before touching disk — there is no unredacted write path."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..policy.redaction import Redactor


class RunLogger:
    def __init__(self, path: Path, redactor: Redactor, run_id: str):
        self.path = Path(path)
        self.redactor = redactor
        self.run_id = run_id
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, event_type: str, **fields: Any) -> dict[str, Any]:
        record: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "event": event_type,
        }
        record.update(fields)
        redacted = self.redactor.redact(record)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(redacted, ensure_ascii=False, default=str) + "\n")
        return redacted
