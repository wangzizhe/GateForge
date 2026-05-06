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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OMC admission for v0.71 non-connector seed candidates.")
    parser.add_argument(
        "--tasks",
        type=Path,
        default=REPO_ROOT / "artifacts" / "non_connector_seed_candidates_v0_71_1" / "tasks.jsonl",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "artifacts" / "non_connector_seed_admission_v0_71_2",
    )
    args = parser.parse_args()
    summary = build_hard_core_adjacent_admission(
        variants=load_jsonl(args.tasks),
        passed_case_ids=set(),
        check_fn=run_omc_admission_check,
        version="v0.71.2",
    )
    write_hard_core_adjacent_admission_outputs(out_dir=args.out_dir, summary=summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
