#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_agent_comparison_protocol_v0_50_0 import run_agent_comparison_protocol  # noqa: E402
from gateforge.agent_modelica_agent_comparison_baseline_summary_v0_50_1 import run_gateforge_comparison_baseline_summary  # noqa: E402
from gateforge.agent_modelica_external_agent_task_bundle_v0_50_2 import run_external_agent_task_bundle  # noqa: E402
from gateforge.agent_modelica_external_agent_result_intake_v0_50_3 import write_external_agent_result_intake_template  # noqa: E402


def main() -> int:
    protocol = run_agent_comparison_protocol()
    baseline = run_gateforge_comparison_baseline_summary()
    bundle = run_external_agent_task_bundle()
    intake = write_external_agent_result_intake_template()
    print(
        json.dumps(
            {
                "protocol_status": protocol["status"],
                "baseline_status": baseline["status"],
                "bundle_status": bundle["status"],
                "intake_status": intake["status"],
            },
            sort_keys=True,
        )
    )
    return 0 if protocol["status"] == "PASS" and bundle["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
