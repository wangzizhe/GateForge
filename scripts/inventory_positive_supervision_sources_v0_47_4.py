#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_positive_supervision_source_inventory_v0_47_4 import (  # noqa: E402
    DEFAULT_ARTIFACT_ROOT,
    DEFAULT_OUT_DIR,
    DEFAULT_QUEUE,
    DEFAULT_TASK_DIR,
    run_positive_supervision_source_inventory,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Inventory positive supervision sources.")
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--task-dir", type=Path, default=DEFAULT_TASK_DIR)
    parser.add_argument("--artifact-root", type=Path, default=DEFAULT_ARTIFACT_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = run_positive_supervision_source_inventory(
        queue_path=args.queue,
        task_dir=args.task_dir,
        artifact_root=args.artifact_root,
        out_dir=args.out_dir,
    )
    print(
        json.dumps(
            {
                "status": summary["status"],
                "case_count": summary["case_count"],
                "source_counts": summary["source_counts"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
