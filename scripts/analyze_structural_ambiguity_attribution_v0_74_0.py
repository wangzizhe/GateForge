from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_structural_ambiguity_attribution_v0_74_0 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    build_structural_ambiguity_attribution,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze v0.74 structural ambiguity budget trajectories.")
    parser.add_argument("--result", action="append", required=True, help="Format: budget_label=path/to/results.jsonl")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--summary-version", default="v0.74.0")
    args = parser.parse_args()
    result_paths_by_budget: dict[str, Path] = {}
    for item in args.result:
        label, sep, path = str(item).partition("=")
        if not sep:
            raise SystemExit(f"Invalid --result value: {item}")
        result_paths_by_budget[label] = Path(path)
    summary = build_structural_ambiguity_attribution(
        result_paths_by_budget=result_paths_by_budget,
        out_dir=args.out_dir,
        summary_version=args.summary_version,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
