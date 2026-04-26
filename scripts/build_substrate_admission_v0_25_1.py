#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_substrate_admission_v0_25_1 import DEFAULT_OUT_DIR, build_substrate_admission


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.25.1 substrate admission gate.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    summary = build_substrate_admission(out_dir=Path(args.out_dir))
    print("status={status} admission={admission_status_counts} blocking={blocking_reason_counts}".format(**summary))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
