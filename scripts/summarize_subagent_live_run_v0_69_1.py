from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from gateforge.agent_modelica_subagent_isolation_v0_69_0 import DEFAULT_OUT_DIR  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize one v0.69.1 live sub-agent run.")
    parser.add_argument("--subagent-summary", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR / "live_run_summary_v0_69_1")
    args = parser.parse_args()

    row = json.loads(args.subagent_summary.read_text(encoding="utf-8"))
    summary = {
        "version": "v0.69.1",
        "analysis_scope": "single_subagent_live_run_summary",
        "evidence_role": "smoke",
        "status": "PASS" if row.get("artifact_complete") else "REVIEW",
        "conclusion_allowed": False,
        "artifact_complete": bool(row.get("artifact_complete")),
        "case_count": 1,
        "subagent_count": 1,
        "subagent_pass_count": 1 if row.get("subagent_verdict") == "PASS" else 0,
        "provider_error_count": 1 if row.get("provider_error") else 0,
        "timeout_count": 1 if row.get("timeout") else 0,
        "budget_exceeded": bool(row.get("budget_exceeded")),
        "token_used": int(row.get("token_used") or 0),
        "candidate_count": int(row.get("candidate_count") or 0),
        "submitted_count": 1 if row.get("submitted") else 0,
        "source_summary": str(args.subagent_summary),
        "discipline": row.get("discipline") or {},
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
