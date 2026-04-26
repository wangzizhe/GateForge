#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_provider_noise_classifier_v0_24_2 import (
    DEFAULT_OUT_DIR,
    build_provider_noise_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze v0.24.2 provider and infra noise.")
    parser.add_argument("--trajectory-path", action="append", dest="trajectory_paths")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    paths = [Path(value) for value in args.trajectory_paths] if args.trajectory_paths else None
    summary = build_provider_noise_report(trajectory_paths=paths, out_dir=Path(args.out_dir))
    print(
        "status={status} observations={observation_count} provider_noise={provider_noise_count} "
        "infra_noise={infra_noise_count} llm_failure={llm_failure_count}".format(**summary)
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
