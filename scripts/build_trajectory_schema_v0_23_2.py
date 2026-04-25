#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_trajectory_schema_v0_23_2 import (
    DEFAULT_OUT_DIR,
    build_trajectory_schema_index,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.23.2 trajectory schema index.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = build_trajectory_schema_index(out_dir=Path(args.out_dir))
    print(
        "status={status} trajectories={trajectory_count} classes={trajectory_class_counts} "
        "validation_errors={validation_error_count}".format(**summary)
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
