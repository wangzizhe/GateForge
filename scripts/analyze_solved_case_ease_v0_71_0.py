from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_benchmark_expansion_v0_71_0 import (  # noqa: E402
    DEFAULT_DIFFICULTY,
    DEFAULT_OUT_DIR,
    DEFAULT_TASKS,
    build_solved_case_ease_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze why solved v0.70 registry cases are easy.")
    parser.add_argument("--difficulty", type=Path, default=DEFAULT_DIFFICULTY)
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = build_solved_case_ease_audit(
        difficulty_path=args.difficulty,
        tasks_path=args.tasks,
        out_dir=args.out_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
