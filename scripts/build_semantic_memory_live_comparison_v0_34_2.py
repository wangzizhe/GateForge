#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_semantic_memory_live_comparison_v0_34_2 import (  # noqa: E402
    DEFAULT_BASELINE_DIR,
    DEFAULT_MEMORY_DIR,
    DEFAULT_OUT_DIR,
    build_semantic_memory_live_comparison,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.34.2 semantic memory live comparison.")
    parser.add_argument("--baseline-dir", type=Path, default=DEFAULT_BASELINE_DIR)
    parser.add_argument("--memory-dir", type=Path, default=DEFAULT_MEMORY_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = build_semantic_memory_live_comparison(
        baseline_dir=args.baseline_dir,
        memory_dir=args.memory_dir,
        out_dir=args.out_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
