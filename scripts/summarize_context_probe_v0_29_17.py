#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_context_probe_summary_v0_29_17 import (  # noqa: E402
    DEFAULT_BASELINE_DIR,
    DEFAULT_CONTEXT_DIR,
    DEFAULT_OUT_DIR,
    build_context_probe_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize Modelica context probe results.")
    parser.add_argument("--baseline-dir", type=Path, default=DEFAULT_BASELINE_DIR)
    parser.add_argument("--context-dir", type=Path, default=DEFAULT_CONTEXT_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    summary = build_context_probe_summary(
        baseline_dir=args.baseline_dir,
        context_dir=args.context_dir,
        out_dir=args.out_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
