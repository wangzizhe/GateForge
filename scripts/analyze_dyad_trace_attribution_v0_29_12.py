#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_dyad_trace_attribution_v0_29_12 import (  # noqa: E402
    DEFAULT_BASE_DIR,
    DEFAULT_CONNECTOR_DIR,
    DEFAULT_OUT_DIR,
    build_dyad_trace_attribution,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Attribute changed cases in Dyad connector A/B traces.")
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR)
    parser.add_argument("--connector-dir", type=Path, default=DEFAULT_CONNECTOR_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    summary = build_dyad_trace_attribution(
        base_dir=args.base_dir,
        connector_dir=args.connector_dir,
        out_dir=args.out_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
