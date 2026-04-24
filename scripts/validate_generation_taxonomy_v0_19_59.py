#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_generation_taxonomy_v0_19_59 import (
    DEFAULT_MAPPING_PATH,
    DEFAULT_NL_TASK_POOL_DIR,
    DEFAULT_OUT_PATH,
    DEFAULT_TAXONOMY_PATH,
    DEFAULT_TRAJECTORY_SOURCES,
    validate_generation_taxonomy,
    write_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate v0.19.59 generation taxonomy and NL task pool.")
    parser.add_argument("--taxonomy", default=str(DEFAULT_TAXONOMY_PATH))
    parser.add_argument("--nl-task-pool", default=str(DEFAULT_NL_TASK_POOL_DIR))
    parser.add_argument("--mapping", default=str(DEFAULT_MAPPING_PATH))
    parser.add_argument("--out", default=str(DEFAULT_OUT_PATH))
    args = parser.parse_args()

    payload = validate_generation_taxonomy(
        taxonomy_path=Path(args.taxonomy),
        nl_task_pool_dir=Path(args.nl_task_pool),
        mapping_path=Path(args.mapping),
        trajectory_sources=DEFAULT_TRAJECTORY_SOURCES,
    )
    out_path = write_summary(payload, Path(args.out))
    print(f"status={payload['status']} out={out_path}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
