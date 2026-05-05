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
    build_equal_budget_ab_summary,
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize v0.69.2 sub-agent equal-budget A/B.")
    parser.add_argument("--single-agent-summary", type=Path, required=True)
    parser.add_argument("--subagent-summary", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR / "equal_budget_ab_v0_69_2")
    parser.add_argument("--budget-total", type=int, default=176000)
    args = parser.parse_args()

    summary = build_equal_budget_ab_summary(
        single_agent_summary=_load_json(args.single_agent_summary),
        subagent_summary=_load_json(args.subagent_summary),
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
