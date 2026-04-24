#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_complex_single_root_repair_benchmark_v0_21_10 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_complex_single_root_repair_benchmark_builder,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.21.10 complex single-root repair benchmark.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = run_complex_single_root_repair_benchmark_builder(out_dir=Path(args.out_dir))
    print(
        "status={status} cases={cases} benchmark={benchmark} next={next_action}".format(
            status=summary["status"],
            cases=summary["case_count"],
            benchmark=summary["benchmark_path"],
            next_action=summary["next_action"],
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
