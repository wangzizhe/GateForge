#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_complex_single_root_admission_v0_21_9 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_complex_single_root_admission,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Admit v0.21.9 complex single-root targets.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = run_complex_single_root_admission(out_dir=Path(args.out_dir))
    print(
        "status={status} candidates={candidates} admitted={admitted} rate={rate} next={next_action} out={out}".format(
            status=summary["status"],
            candidates=summary["candidate_count"],
            admitted=summary["admitted_count"],
            rate=summary["admission_pass_rate"],
            next_action=summary["next_action"],
            out=Path(args.out_dir),
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
