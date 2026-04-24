#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_search_density_synthesis_v0_20_5 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    build_search_density_synthesis,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.20.5 search-density synthesis.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = build_search_density_synthesis(out_dir=Path(args.out_dir))
    decisions = summary.get("decisions") or {}
    print(
        "status={status} default={default} next={next_phase} conclusion={conclusion} out={out}".format(
            status=summary.get("status"),
            default=decisions.get("default_strategy"),
            next_phase=decisions.get("next_phase"),
            conclusion=summary.get("conclusion"),
            out=Path(args.out_dir),
        )
    )
    return 0 if summary.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
