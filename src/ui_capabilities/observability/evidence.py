"""Deterministic evidence paths per run: JSONL log, screenshots, traces."""

from __future__ import annotations

from pathlib import Path


class EvidenceManager:
    def __init__(self, base_dir: Path, run_id: str):
        self.run_id = run_id
        self.run_dir = Path(base_dir) / "runs" / run_id
        self.screenshot_dir = self.run_dir / "screenshots"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    @property
    def log_path(self) -> Path:
        return self.run_dir / "run.jsonl"

    @property
    def trace_path(self) -> Path:
        return self.run_dir / "trace.zip"

    def screenshot_path(self, label: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in label)
        return self.screenshot_dir / f"{safe}.png"

    def files(self) -> list[str]:
        return sorted(str(p) for p in self.run_dir.rglob("*") if p.is_file())
