#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_dyad_ab_summary_v0_29_11 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    build_dyad_ab_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize Dyad methodology A/B result directories.")
    parser.add_argument("--base-dir", type=Path, required=True)
    parser.add_argument("--structural-dir", type=Path, required=True)
    parser.add_argument("--connector-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    summary = build_dyad_ab_summary(
        arm_dirs={
            "base": args.base_dir,
            "structural": args.structural_dir,
            "connector": args.connector_dir,
        },
        out_dir=args.out_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
