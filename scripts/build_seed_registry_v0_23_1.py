#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_seed_registry_v0_23_1 import DEFAULT_OUT_DIR, build_seed_registry


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.23.1 seed registry.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = build_seed_registry(out_dir=Path(args.out_dir))
    print(
        "status={status} seeds={seed_count} policies={registry_policy_counts} families={family_counts}".format(
            **summary
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
