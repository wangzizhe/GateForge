from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_structural_ambiguity_benchmark_v0_72_0 import (  # noqa: E402
    summarize_budget_calibration,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize v0.72 structural ambiguity budget calibration.")
    parser.add_argument("--result", action="append", required=True, help="Format: budget_label=path/to/results.jsonl")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--summary-version", default="v0.72.5")
    args = parser.parse_args()
    result_paths_by_budget: dict[str, Path] = {}
    for item in args.result:
        label, sep, path = str(item).partition("=")
        if not sep:
            raise SystemExit(f"Invalid --result value: {item}")
        result_paths_by_budget[label] = Path(path)
    summary = summarize_budget_calibration(
        result_paths_by_budget=result_paths_by_budget,
        out_dir=args.out_dir,
        summary_version=args.summary_version,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
