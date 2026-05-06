from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_full_registry_baseline_v0_70_0 import (  # noqa: E402
    DEFAULT_REGISTRY,
    merge_workspace_results,
    summarize_full_registry_baseline,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize v0.70 full registry baseline results.")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--results", type=Path, action="append", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--summary-version", default="v0.70.1")
    args = parser.parse_args()
    merged_results = args.out_dir / "merged_results.jsonl"
    merge_workspace_results(result_paths=list(args.results or []), out_path=merged_results)
    summary = summarize_full_registry_baseline(
        registry_path=args.registry,
        results_path=merged_results,
        out_dir=args.out_dir,
        summary_version=args.summary_version,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
