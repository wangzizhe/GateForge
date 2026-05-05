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
    build_hard_pack_subagent_readiness_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize v0.69.4 hard-pack sub-agent readiness.")
    parser.add_argument("--contract-summary", type=Path, required=True)
    parser.add_argument("--equal-budget-summary", type=Path, required=True)
    parser.add_argument("--provider-stable", action="store_true")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR / "hard_pack_readiness_v0_69_4")
    args = parser.parse_args()

    contract = json.loads(args.contract_summary.read_text(encoding="utf-8"))
    equal_budget = json.loads(args.equal_budget_summary.read_text(encoding="utf-8"))
    summary = build_hard_pack_subagent_readiness_summary(
        contract_summary=contract,
        equal_budget_summary=equal_budget,
        provider_stable=bool(args.provider_stable),
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
