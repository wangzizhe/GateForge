#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_search_density_v0_20_0 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    build_search_density_substrate,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.20.0 search-density substrate.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--broadened-target-max-cases", type=int, default=40)
    args = parser.parse_args()

    substrate = build_search_density_substrate(
        out_dir=Path(args.out_dir),
        broadened_target_max_cases=args.broadened_target_max_cases,
    )
    summary = substrate["summary"]
    print(
        "status={status} main={main} shadow={shadow} total={total} out={out}".format(
            status=summary.get("status"),
            main=summary.get("main_case_count"),
            shadow=summary.get("shadow_case_count"),
            total=summary.get("case_count"),
            out=Path(args.out_dir),
        )
    )
    return 0 if summary.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
