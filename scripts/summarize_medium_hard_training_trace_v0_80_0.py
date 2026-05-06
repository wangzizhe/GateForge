from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_medium_hard_training_trace_v0_80_0 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    DEFAULT_PACK_TASKS,
    build_medium_hard_training_trace_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.80 medium-hard failure taxonomy and training trace schema.")
    parser.add_argument("--tasks", type=Path, default=DEFAULT_PACK_TASKS)
    parser.add_argument("--result", action="append", required=True, help="Format: arm_label=path/to/results.jsonl")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--summary-version", default="v0.80.0")
    args = parser.parse_args()
    result_paths_by_arm: dict[str, Path] = {}
    for item in args.result:
        label, sep, path = str(item).partition("=")
        if not sep:
            raise SystemExit(f"Invalid --result value: {item}")
        result_paths_by_arm[label] = Path(path)
    summary = build_medium_hard_training_trace_summary(
        tasks_path=args.tasks,
        result_paths_by_arm=result_paths_by_arm,
        out_dir=args.out_dir,
        summary_version=args.summary_version,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
