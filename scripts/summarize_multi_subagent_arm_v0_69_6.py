from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_subagent_isolation_v0_69_0 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    build_multi_subagent_arm_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize a v0.69 multi-subagent arm.")
    parser.add_argument("--subagent-summary", type=Path, action="append", required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR / "multi_subagent_arm_v0_69_6")
    parser.add_argument("--budget-total", type=int, default=96000)
    args = parser.parse_args()

    rows = [json.loads(path.read_text(encoding="utf-8")) for path in args.subagent_summary]
    summary = build_multi_subagent_arm_summary(
        subagent_summaries=rows,
        budget_total=args.budget_total,
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
