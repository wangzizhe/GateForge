from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_structural_ambiguity_benchmark_v0_72_0 import (  # noqa: E402
    DEFAULT_MEDIUM_HARD_PACK_OUT_DIR,
    build_medium_hard_pack,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.75 strict medium-hard benchmark pack.")
    parser.add_argument("--task", action="append", type=Path, required=True)
    parser.add_argument("--repeatability-summary", action="append", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_MEDIUM_HARD_PACK_OUT_DIR)
    parser.add_argument("--summary-version", default="v0.75.5")
    args = parser.parse_args()
    summary = build_medium_hard_pack(
        task_paths=list(args.task or []),
        repeatability_summary_paths=list(args.repeatability_summary or []),
        out_dir=args.out_dir,
        summary_version=args.summary_version,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
