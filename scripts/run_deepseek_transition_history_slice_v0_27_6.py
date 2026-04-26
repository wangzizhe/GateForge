#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

os.environ.setdefault("GATEFORGE_AGENT_LIVE_MAX_REQUESTS_PER_RUN", "18")
os.environ.setdefault("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC", "180")

from gateforge.agent_modelica_deepseek_transition_history_slice_v0_27_6 import (  # noqa: E402
    DEFAULT_OUT_DIR,
    run_deepseek_transition_history_slice,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.27.6 DeepSeek transition-history source-backed slice.")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--max-rounds", type=int, default=3)
    args = parser.parse_args()
    summary = run_deepseek_transition_history_slice(
        out_dir=Path(args.out_dir),
        limit=max(0, int(args.limit)),
        max_rounds=max(1, int(args.max_rounds)),
        planner_backend="auto",
    )
    print(
        "status={status} decision={decision} cases={case_count} pass={pass_count} "
        "true_multi={true_multi_turn_count} provider_errors={provider_error_count}".format(**summary)
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
