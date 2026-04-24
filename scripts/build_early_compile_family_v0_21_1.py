#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_early_compile_family_v0_21_1 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_early_compile_family_builder,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build v0.21.1 early compile family candidates.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    summary = run_early_compile_family_builder(out_dir=Path(args.out_dir))
    print(
        "status={status} candidates={candidates} ready={ready} next={next_action} out={out}".format(
            status=summary["status"],
            candidates=summary["family_candidate_count"],
            ready=summary["ready_for_admission_audit_count"],
            next_action=summary["next_action"],
            out=Path(args.out_dir),
        )
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
