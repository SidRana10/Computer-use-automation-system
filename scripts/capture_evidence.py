#!/usr/bin/env python3
"""Capture the canonical submission evidence set.

Runs (against a demo app already listening on --target):
  1. genuine LLM-driven discovery of member.get_savings_balance (M-10001)
     — Gemini by default (free tier); Anthropic via --provider anthropic
  2. deterministic replay with a DIFFERENT member (M-10003)  -> success
  3. replay with unknown member (M-40400)                    -> business outcome
  4. replay with injected missing-control failure            -> hard failure + screenshot

and copies the results to the canonical /evidence paths:
  evidence/discovery_run.jsonl
  evidence/discovery_trace.zip        (if tracing produced one)
  evidence/example_capability.json
  evidence/replay_success.jsonl
  evidence/replay_not_found.jsonl
  evidence/replay_failure.jsonl
  evidence/failure_screenshot.png

Genuine mode FAILS LOUDLY if the selected provider's API key is absent
(GEMINI_API_KEY for gemini, ANTHROPIC_API_KEY for anthropic) and NEVER falls
back to a scripted model. --fake exercises the same plumbing with the scripted
test double and writes to evidence-dryrun/ instead: it can NEVER produce the
genuine discovery evidence.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUN_DIR_RE = re.compile(r"^evidence: (.+)$", re.MULTILINE)
ARTIFACT_RE = re.compile(r"^artifact: (.+)$", re.MULTILINE)


def run_uicap(args: list[str]) -> tuple[int, str]:
    cmd = [sys.executable, "-m", "ui_capabilities.cli", *args]
    print(f"\n$ uicap {' '.join(args)}")
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{REPO / 'src'}{os.pathsep}{REPO}" + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    proc = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, env=env)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode, proc.stdout


def extract_run_dir(stdout: str) -> Path:
    match = RUN_DIR_RE.search(stdout)
    if not match:
        raise SystemExit("could not find evidence run dir in command output")
    return REPO / match.group(1).strip()


def copy(src: Path, dst: Path, required: bool = True) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  copied {src} -> {dst}")
    elif required:
        raise SystemExit(f"expected evidence file missing: {src}")


def reset_demo(target: str) -> None:
    request = urllib.request.Request(f"{target.rstrip('/')}/demo/reset", method="POST")
    urllib.request.urlopen(request, timeout=10).read()


REQUIRED_KEY_BY_PROVIDER = {"gemini": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


def require_genuine_provider(provider: str) -> None:
    """Fail loudly (no fake fallback, ever) if genuine discovery cannot run."""
    if provider not in REQUIRED_KEY_BY_PROVIDER:
        raise SystemExit(
            f"unknown provider {provider!r}; genuine evidence supports {sorted(REQUIRED_KEY_BY_PROVIDER)} "
            "(the scripted test double is not a genuine provider)"
        )
    key_name = REQUIRED_KEY_BY_PROVIDER[provider]
    if not os.environ.get(key_name):
        raise SystemExit(
            f"{key_name} is not set: genuine evidence capture with provider {provider!r} cannot run.\n"
            "Refusing to fall back to a scripted model — set the key and re-run.\n"
            "(Gemini free-tier keys: https://aistudio.google.com/apikey)"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default="http://127.0.0.1:8001")
    parser.add_argument(
        "--provider",
        choices=["gemini", "anthropic"],
        default=(os.environ.get("LLM_PROVIDER") or "gemini").strip().lower(),
        help="genuine discovery provider (default: LLM_PROVIDER env, gemini)",
    )
    parser.add_argument("--fake", action="store_true", help="dry-run with the scripted test double (NOT valid discovery evidence)")
    parser.add_argument("--headless", action="store_true", help="run browsers headless")
    args = parser.parse_args()

    # load .env the same way the CLI does, so key checks see it
    try:
        from dotenv import load_dotenv

        load_dotenv(REPO / ".env", override=False)
    except ImportError:
        pass

    if not args.fake:
        require_genuine_provider(args.provider)

    out_root = REPO / ("evidence-dryrun" if args.fake else "evidence")
    artifact_path = REPO / "artifacts" / "member.get_savings_balance.v1.json"
    headless = ["--headless"] if args.headless else []

    try:
        urllib.request.urlopen(args.target, timeout=5)
    except Exception:
        raise SystemExit(f"demo app is not reachable at {args.target}; start it first: uicap demo-app")

    reset_demo(args.target)

    # 1. discovery — the adapter is always explicit: the scripted double only
    # ever runs when --fake was requested, never as a fallback
    adapter = ["--model-adapter", "fake" if args.fake else args.provider]
    code, stdout = run_uicap(
        [
            "discover",
            "--goal", "Look up member M-10001 and return their current savings balance.",
            "--target", args.target,
            "--capability-id", "member.get_savings_balance",
            "--input", "member_id=M-10001",
            "--output", str(artifact_path),
            "--no-operator",
            *adapter,
            *headless,
        ]
    )
    if code != 0:
        raise SystemExit(f"discovery failed (exit {code}); no evidence captured")
    disc_dir = extract_run_dir(stdout)
    copy(disc_dir / "run.jsonl", out_root / "discovery_run.jsonl")
    copy(disc_dir / "trace.zip", out_root / "discovery_trace.zip", required=False)
    copy(artifact_path, out_root / "example_capability.json")

    # 2. deterministic replay with a different member
    reset_demo(args.target)
    code, stdout = run_uicap(["replay", "--artifact", str(artifact_path), "--input", "member_id=M-10003", "--no-operator", *headless])
    if code != 0:
        raise SystemExit(f"success replay unexpectedly failed (exit {code})")
    copy(extract_run_dir(stdout) / "run.jsonl", out_root / "replay_success.jsonl")

    # 3. business outcome
    reset_demo(args.target)
    code, stdout = run_uicap(["replay", "--artifact", str(artifact_path), "--input", "member_id=M-40400", "--no-operator", *headless])
    copy(extract_run_dir(stdout) / "run.jsonl", out_root / "replay_not_found.jsonl")

    # 4. injected hard failure
    reset_demo(args.target)
    code, stdout = run_uicap(
        ["replay", "--artifact", str(artifact_path), "--input", "member_id=M-10003", "--demo-failure", "missing_accounts_control", "--no-operator", *headless]
    )
    fail_dir = extract_run_dir(stdout)
    copy(fail_dir / "run.jsonl", out_root / "replay_failure.jsonl")
    screenshots = sorted((fail_dir / "screenshots").glob("failure_*.png"))
    if not screenshots:
        raise SystemExit("no failure screenshot was captured")
    copy(screenshots[0], out_root / "failure_screenshot.png")
    reset_demo(args.target)

    kind = "DRY-RUN (fake model — not valid discovery evidence)" if args.fake else "GENUINE"
    print(f"\n{kind} evidence captured under {out_root}/")


if __name__ == "__main__":
    main()
