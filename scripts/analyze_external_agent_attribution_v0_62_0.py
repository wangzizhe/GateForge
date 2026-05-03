from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_external_agent_attribution_v0_62_0 import (
    DEFAULT_EXTERNAL_RESULTS_DIR,
    DEFAULT_EXTERNAL_VERIFICATION,
    DEFAULT_GATEFORGE_RESULTS,
    DEFAULT_OUT_DIR,
    run_external_agent_attribution,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze external Agent attribution on the solvable holdout.")
    parser.add_argument("--gateforge-results", type=Path, default=DEFAULT_GATEFORGE_RESULTS)
    parser.add_argument("--external-results-dir", type=Path, default=DEFAULT_EXTERNAL_RESULTS_DIR)
    parser.add_argument("--external-verification", type=Path, default=DEFAULT_EXTERNAL_VERIFICATION)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    summary = run_external_agent_attribution(
        gateforge_results_path=args.gateforge_results,
        external_results_dir=args.external_results_dir,
        external_verification_path=args.external_verification,
        out_dir=args.out_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
