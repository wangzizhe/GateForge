#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_repair_history_contract_v0_27_5 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    build_repair_history_contract_summary,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.27.5 repair history transition contract artifact.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()
    summary = build_repair_history_contract_summary(out_dir=Path(args.out_dir))
    print(
        "status={status} decision={decision} input_transition={contains_input_omc_summary} "
        "post_transition={contains_post_patch_omc_summary}".format(**summary)
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
