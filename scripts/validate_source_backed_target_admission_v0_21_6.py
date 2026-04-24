#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_source_backed_target_admission_v0_21_6 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_source_backed_target_admission,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate v0.21.6 source-backed target admission.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = run_source_backed_target_admission(out_dir=Path(args.out_dir))
    print(
        "status={status} validated={validated} main={main} blocked={blocked} decision={decision} out={out}".format(
            status=summary["status"],
            validated=summary["validated_candidate_count"],
            main=summary["main_admissible_count"],
            blocked=summary["blocked_from_main_benchmark_count"],
            decision=summary["benchmark_admission_decision"],
            out=Path(args.out_dir),
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
