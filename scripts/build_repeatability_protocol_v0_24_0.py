#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_repeatability_protocol_v0_24_0 import (
    DEFAULT_OUT_DIR,
    DEFAULT_SEED_REGISTRY_PATH,
    DEFAULT_TRAJECTORY_PATH,
    build_repeatability_protocol,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.24.0 repeatability protocol.")
    parser.add_argument("--seed-registry-path", default=str(DEFAULT_SEED_REGISTRY_PATH))
    parser.add_argument("--trajectory-path", default=str(DEFAULT_TRAJECTORY_PATH))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = build_repeatability_protocol(
        seed_registry_path=Path(args.seed_registry_path),
        trajectory_path=Path(args.trajectory_path),
        out_dir=Path(args.out_dir),
    )
    print(
        "status={status} candidates={candidate_count} families={family_count} "
        "candidate_classes={candidate_repeatability_counts}".format(**summary)
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
