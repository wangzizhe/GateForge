from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_full_registry_baseline_v0_70_0 import (  # noqa: E402
    summarize_hard_candidate_repeatability,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize v0.70 hard-candidate repeatability results.")
    parser.add_argument("--baseline-summary", type=Path, required=True)
    parser.add_argument("--repeat-results", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--summary-version", default="v0.70.2")
    args = parser.parse_args()
    summary = summarize_hard_candidate_repeatability(
        baseline_summary_path=args.baseline_summary,
        repeat_results_path=args.repeat_results,
        out_dir=args.out_dir,
        summary_version=args.summary_version,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
