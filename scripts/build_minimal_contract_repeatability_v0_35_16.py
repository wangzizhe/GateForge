#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_minimal_contract_repeatability_v0_35_16 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    build_minimal_contract_repeatability,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the v0.35.16 minimal contract repeatability summary.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = build_minimal_contract_repeatability(out_dir=args.out_dir)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
