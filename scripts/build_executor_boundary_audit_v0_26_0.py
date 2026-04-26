#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_executor_boundary_audit_v0_26_0 import (
    DEFAULT_OUT_DIR,
    build_executor_boundary_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.26.0 executor boundary audit.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    summary = build_executor_boundary_audit(out_dir=Path(args.out_dir))
    print("status={status} decision={decision} next={next_focus}".format(**summary))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
