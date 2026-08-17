#!/usr/bin/env python3
"""Write the fixture artifact for the risky sub-account handoff demo.

This artifact is hand-authored (equivalent to compiled output, schema-valid);
its provenance says so. The genuine-discovery requirement is satisfied by the
balance capability; the handoff demo only needs a capability whose final step
is irreversible. It can also be produced via
`uicap discover --model-adapter fake-subaccount` if you prefer.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO))

from tests.fixtures.factories import make_subaccount_artifact  # noqa: E402
from ui_capabilities.discovery.compiler import save_artifact  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default="http://127.0.0.1:8001")
    parser.add_argument("--output", default=str(REPO / "artifacts" / "member.open_sub_account.v1.json"))
    args = parser.parse_args()
    artifact = make_subaccount_artifact(args.target)
    save_artifact(artifact, args.output)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
