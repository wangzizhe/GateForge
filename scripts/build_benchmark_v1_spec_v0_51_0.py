from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_benchmark_v1_spec_v0_51_0 import run_benchmark_v1_spec  # noqa: E402


def main() -> int:
    summary = run_benchmark_v1_spec()
    print(json.dumps({"status": summary["status"], "readiness_status": summary["readiness_status"]}, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
