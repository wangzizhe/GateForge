#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_semantic_memory_focus_v0_34_6 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    build_semantic_memory_focus,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.34.6 focused semantic memory context.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--unit-id", action="append", default=[])
    args = parser.parse_args()
    summary = build_semantic_memory_focus(out_dir=args.out_dir, unit_ids=list(args.unit_id or []) or None)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
