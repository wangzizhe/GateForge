#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_complex_single_root_pack_v0_21_8 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_complex_single_root_pack,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.21.8 complex single-root candidate pack.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--limit", type=int, default=9)
    args = parser.parse_args()

    summary = run_complex_single_root_pack(out_dir=Path(args.out_dir), limit=args.limit)
    print(
        "status={status} candidates={candidates} min_impacts={impacts} next={next_action} out={out}".format(
            status=summary["status"],
            candidates=summary["candidate_count"],
            impacts=summary["minimum_impact_point_count"],
            next_action=summary["next_action"],
            out=Path(args.out_dir),
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
