#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_runner_artifact_contract_v0_23_4 import (
    DEFAULT_OUT_DIR,
    build_runner_artifact_contract,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.23.4 runner artifact contract.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = build_runner_artifact_contract(out_dir=Path(args.out_dir))
    print(
        "status={status} manifests={manifest_count} validation_errors={validation_error_count}".format(
            **summary
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
