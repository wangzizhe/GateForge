#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_mutation_candidate_distill_v0_19_61 import (  # noqa: E402
    DEFAULT_INPUT_DIR,
    DEFAULT_OUT_DIR,
    run_mutation_candidate_distill,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Distill v0.19.61 mutation candidates from generation failures.")
    parser.add_argument("--input-dir", default=str(DEFAULT_INPUT_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    summary = run_mutation_candidate_distill(
        input_dir=Path(args.input_dir),
        out_dir=Path(args.out_dir),
    )
    print(
        "status={status} candidates={candidates} admitted={admitted} pass_rate={rate} out={out}".format(
            status=summary.get("status"),
            candidates=summary.get("candidate_count"),
            admitted=summary.get("admitted_count"),
            rate=summary.get("admission_pass_rate"),
            out=Path(args.out_dir),
        )
    )
    return 0 if summary.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

