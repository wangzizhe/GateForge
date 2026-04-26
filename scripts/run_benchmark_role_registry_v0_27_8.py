#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_benchmark_role_registry_v0_27_8 import (  # noqa: E402
    DEFAULT_HARD_NEGATIVE_SUMMARY,
    DEFAULT_MANIFEST,
    DEFAULT_OUT_DIR,
    DEFAULT_REPEATABILITY_SUMMARY,
    run_benchmark_role_registry,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.27.8 benchmark role registry.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--repeatability-summary", default=str(DEFAULT_REPEATABILITY_SUMMARY))
    parser.add_argument("--hard-negative-summary", default=str(DEFAULT_HARD_NEGATIVE_SUMMARY))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    summary = run_benchmark_role_registry(
        manifest_path=Path(args.manifest),
        repeatability_summary_path=Path(args.repeatability_summary),
        hard_negative_summary_path=Path(args.hard_negative_summary),
        out_dir=Path(args.out_dir),
    )
    print(
        "status={status} decision={decision} families={family_count} roles={role_counts}".format(**summary)
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
