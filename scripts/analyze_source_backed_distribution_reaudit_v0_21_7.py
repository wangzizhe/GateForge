#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_source_backed_distribution_reaudit_v0_21_7 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_source_backed_distribution_reaudit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze v0.21.7 source-backed distribution re-audit.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = run_source_backed_distribution_reaudit(out_dir=Path(args.out_dir))
    print(
        "status={status} previous={previous} updated={updated} delta={delta} main={main} out={out}".format(
            status=summary["status"],
            previous=summary["previous_distance"],
            updated=summary["updated_distance"],
            delta=summary["distance_delta"],
            main=summary["main_admissible_count"],
            out=Path(args.out_dir),
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
