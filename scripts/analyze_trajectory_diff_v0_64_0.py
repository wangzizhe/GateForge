from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_trajectory_diff_v0_64_0 import (
    DEFAULT_ATTRIBUTION,
    DEFAULT_EXTERNAL_RESULTS_DIR,
    DEFAULT_GATEFORGE_RESULTS,
    DEFAULT_OUT_DIR,
    run_trajectory_diff,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze observable GateForge/external agent trajectory differences.")
    parser.add_argument("--gateforge-results", type=Path, default=DEFAULT_GATEFORGE_RESULTS)
    parser.add_argument("--external-results-dir", type=Path, default=DEFAULT_EXTERNAL_RESULTS_DIR)
    parser.add_argument("--attribution", type=Path, default=DEFAULT_ATTRIBUTION)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = run_trajectory_diff(
        gateforge_results_path=args.gateforge_results,
        external_results_dir=args.external_results_dir,
        attribution_path=args.attribution,
        out_dir=args.out_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
