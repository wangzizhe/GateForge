#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_benchmark_slice_plan_v0_27_9 import (  # noqa: E402
    DEFAULT_MANIFEST,
    DEFAULT_OUT_DIR,
    DEFAULT_ROLE_REGISTRY,
    run_benchmark_slice_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.27.9 role-separated benchmark slice plan.")
    parser.add_argument("--role-registry", default=str(DEFAULT_ROLE_REGISTRY))
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--max-per-slice", type=int, default=3)
    args = parser.parse_args()
    summary = run_benchmark_slice_plan(
        role_registry_path=Path(args.role_registry),
        manifest_path=Path(args.manifest),
        out_dir=Path(args.out_dir),
        max_per_slice=max(0, int(args.max_per_slice)),
    )
    print(
        "status={status} decision={decision} planned={planned_case_count} slices={slice_counts}".format(**summary)
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
