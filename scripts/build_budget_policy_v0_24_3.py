#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_budget_policy_v0_24_3 import DEFAULT_OUT_DIR, build_budget_policy_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.24.3 budget and timeout policy.")
    parser.add_argument("--manifest-path", action="append", dest="manifest_paths")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    paths = [Path(value) for value in args.manifest_paths] if args.manifest_paths else None
    summary = build_budget_policy_report(manifest_paths=paths, out_dir=Path(args.out_dir))
    print(
        "status={status} modes={policy_modes} manifests={manifest_count} "
        "validation_errors={validation_error_count}".format(**summary)
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
