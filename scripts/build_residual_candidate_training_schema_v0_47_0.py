#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_residual_candidate_training_schema_v0_47_0 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    DEFAULT_SUBSTRATE,
    run_residual_candidate_training_schema,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build residual-to-candidate mapping training schema.")
    parser.add_argument("--substrate", type=Path, default=DEFAULT_SUBSTRATE)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = run_residual_candidate_training_schema(substrate_path=args.substrate, out_dir=args.out_dir)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "training_example_count": summary["training_example_count"],
                "mapping_gap_label_counts": summary["mapping_gap_label_counts"],
                "conclusion_allowed": summary["conclusion_allowed"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
