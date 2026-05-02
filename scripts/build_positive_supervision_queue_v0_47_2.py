#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_positive_supervision_queue_v0_47_2 import (  # noqa: E402
    DEFAULT_EXAMPLES,
    DEFAULT_OUT_DIR,
    run_positive_supervision_queue,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build positive supervision annotation queue.")
    parser.add_argument("--examples", type=Path, default=DEFAULT_EXAMPLES)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = run_positive_supervision_queue(examples_path=args.examples, out_dir=args.out_dir)
    print(
        json.dumps(
            {
                "status": summary["status"],
                "queue_case_count": summary["queue_case_count"],
                "label_status_counts": summary["label_status_counts"],
            },
            sort_keys=True,
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
