#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p artifacts/governance_promote_demo

bash scripts/demo_governance_snapshot.sh

python3 -m gateforge.governance_promote \
  --snapshot artifacts/governance_snapshot_demo/summary.json \
  --profile default \
  --out artifacts/governance_promote_demo/default.json \
  --report artifacts/governance_promote_demo/default.md

set +e
python3 -m gateforge.governance_promote \
  --snapshot artifacts/governance_snapshot_demo/summary.json \
  --profile industrial_strict \
  --out artifacts/governance_promote_demo/industrial.json \
  --report artifacts/governance_promote_demo/industrial.md
INDUSTRIAL_EXIT=$?
set -e

INDUSTRIAL_EXIT="$INDUSTRIAL_EXIT" python3 - <<'PY'
import json
import os
from pathlib import Path

default_payload = json.loads(Path("artifacts/governance_promote_demo/default.json").read_text(encoding="utf-8"))
industrial_payload = json.loads(Path("artifacts/governance_promote_demo/industrial.json").read_text(encoding="utf-8"))
industrial_exit = int(os.environ.get("INDUSTRIAL_EXIT", "1"))

summary = {
    "default_decision": default_payload.get("decision"),
    "industrial_decision": industrial_payload.get("decision"),
    "industrial_exit_code": industrial_exit,
}
summary["result_flags"] = {
    "default_expected_non_fail": "PASS" if summary["default_decision"] in {"PASS", "NEEDS_REVIEW"} else "FAIL",
    "industrial_expected_fail": "PASS" if summary["industrial_decision"] == "FAIL" and industrial_exit != 0 else "FAIL",
}
summary["bundle_status"] = "PASS" if all(v == "PASS" for v in summary["result_flags"].values()) else "FAIL"

Path("artifacts/governance_promote_demo/summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
Path("artifacts/governance_promote_demo/summary.md").write_text(
    "\n".join(
        [
            "# Governance Promote Demo",
            "",
            f"- default_decision: `{summary['default_decision']}`",
            f"- industrial_decision: `{summary['industrial_decision']}`",
            f"- industrial_exit_code: `{summary['industrial_exit_code']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- default_expected_non_fail: `{summary['result_flags']['default_expected_non_fail']}`",
            f"- industrial_expected_fail: `{summary['result_flags']['industrial_expected_fail']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": summary["bundle_status"]}))
PY

cat artifacts/governance_promote_demo/summary.json
cat artifacts/governance_promote_demo/summary.md

python3 - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("artifacts/governance_promote_demo/summary.json").read_text(encoding="utf-8"))
if payload.get("bundle_status") != "PASS":
    raise SystemExit(1)
PY
