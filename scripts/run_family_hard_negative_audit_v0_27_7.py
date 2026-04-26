#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_family_hard_negative_audit_v0_27_7 import (  # noqa: E402
    DEFAULT_CANDIDATES,
    DEFAULT_OUT_DIR,
    DEFAULT_RESULTS,
    run_family_hard_negative_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit v0.27.7 family hard-negative status.")
    parser.add_argument("--candidates", default=str(DEFAULT_CANDIDATES))
    parser.add_argument("--results", default=str(DEFAULT_RESULTS))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    summary = run_family_hard_negative_audit(
        candidates_path=Path(args.candidates),
        results_path=Path(args.results),
        out_dir=Path(args.out_dir),
    )
    print(
        "status={status} decision={decision} cases={audited_case_count} pass={pass_count} "
        "hard_negative={hard_negative_signal_count} stalled={final_round_stall_count}".format(**summary)
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
