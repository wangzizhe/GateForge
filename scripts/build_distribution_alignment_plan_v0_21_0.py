#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_distribution_alignment_plan_v0_21_0 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_distribution_alignment_plan,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.21.0 distribution-alignment plan.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = run_distribution_alignment_plan(out_dir=Path(args.out_dir))
    print(
        "status={status} distance={distance} target_candidates={candidates} next={next_action} out={out}".format(
            status=summary["status"],
            distance=summary["current_distribution_distance"],
            candidates=summary["target_isolated_candidate_count"],
            next_action=summary["next_action"],
            out=Path(args.out_dir),
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
