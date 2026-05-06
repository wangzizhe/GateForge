from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_hard_core_adjacent_admission_v0_48_3 import (  # noqa: E402
    build_hard_core_adjacent_admission,
    run_omc_admission_check,
    write_hard_core_adjacent_admission_outputs,
)
from gateforge.agent_modelica_hard_core_training_substrate_v0_43_0 import load_jsonl  # noqa: E402
from gateforge.agent_modelica_structural_ambiguity_benchmark_v0_72_0 import (  # noqa: E402
    DEFAULT_STABLE_PATTERN_EXPANSION_OUT_DIR,
)


DEFAULT_OUT_DIR = REPO_ROOT / "artifacts" / "structural_ambiguity_stable_pattern_admission_v0_76_1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OMC admission for v0.76 stable-pattern candidates.")
    parser.add_argument("--tasks", type=Path, default=DEFAULT_STABLE_PATTERN_EXPANSION_OUT_DIR / "tasks.jsonl")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = build_hard_core_adjacent_admission(
        variants=load_jsonl(args.tasks),
        passed_case_ids=set(),
        check_fn=run_omc_admission_check,
        version="v0.76.1",
    )
    summary["analysis_scope"] = "structural_ambiguity_stable_pattern_omc_admission"
    summary["status"] = "PASS" if summary.get("case_count") == summary.get("admitted_case_count") else "REVIEW"
    write_hard_core_adjacent_admission_outputs(out_dir=args.out_dir, summary=summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
