#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_harness_contract_synthesis_v0_23_6 import (
    DEFAULT_OUT_DIR,
    build_harness_contract_synthesis,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.23.6 harness contract synthesis.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = build_harness_contract_synthesis(out_dir=Path(args.out_dir))
    print(
        "status={status} decision={phase_decision} ready_for_v0_24={ready_for_v0_24_repeatability_replay}".format(
            **summary
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
