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

python3 - <<'PY'
import json
from pathlib import Path

source = json.loads(Path("artifacts/governance_snapshot_demo/summary.json").read_text(encoding="utf-8"))
kpis = source.get("kpis", {}) if isinstance(source.get("kpis"), dict) else {}
kpis["recommended_profile"] = "industrial_strict"
source["kpis"] = kpis
Path("artifacts/governance_promote_demo/snapshot_mismatch.json").write_text(
    json.dumps(source, indent=2), encoding="utf-8"
)
PY

python3 -m gateforge.governance_promote \
  --snapshot artifacts/governance_promote_demo/snapshot_mismatch.json \
  --profile default \
  --out artifacts/governance_promote_demo/mismatch_default.json \
  --report artifacts/governance_promote_demo/mismatch_default.md

cat > artifacts/governance_promote_demo/override_allow_promote.json <<'JSON'
{
  "allow_promote": true,
  "reason": "human waiver approved for rollout window",
  "approved_by": "review.committee",
  "expires_utc": "2099-01-01T00:00:00Z"
}
JSON

python3 -m gateforge.governance_promote \
  --snapshot artifacts/governance_snapshot_demo/summary.json \
  --profile industrial_strict \
  --override artifacts/governance_promote_demo/override_allow_promote.json \
  --out artifacts/governance_promote_demo/override.json \
  --report artifacts/governance_promote_demo/override.md

set +e
python3 -m gateforge.governance_promote \
  --snapshot artifacts/governance_snapshot_demo/summary.json \
  --profile industrial_strict \
  --out artifacts/governance_promote_demo/industrial.json \
  --report artifacts/governance_promote_demo/industrial.md
INDUSTRIAL_EXIT=$?

python3 -m gateforge.governance_promote \
  --snapshot artifacts/governance_promote_demo/snapshot_mismatch.json \
  --profile industrial_strict \
  --out artifacts/governance_promote_demo/mismatch_industrial.json \
  --report artifacts/governance_promote_demo/mismatch_industrial.md
MISMATCH_INDUSTRIAL_EXIT=$?
set -e

INDUSTRIAL_EXIT="$INDUSTRIAL_EXIT" MISMATCH_INDUSTRIAL_EXIT="$MISMATCH_INDUSTRIAL_EXIT" python3 - <<'PY'
import json
import os
from pathlib import Path

default_payload = json.loads(Path("artifacts/governance_promote_demo/default.json").read_text(encoding="utf-8"))
industrial_payload = json.loads(Path("artifacts/governance_promote_demo/industrial.json").read_text(encoding="utf-8"))
override_payload = json.loads(Path("artifacts/governance_promote_demo/override.json").read_text(encoding="utf-8"))
mismatch_default_payload = json.loads(Path("artifacts/governance_promote_demo/mismatch_default.json").read_text(encoding="utf-8"))
mismatch_industrial_payload = json.loads(Path("artifacts/governance_promote_demo/mismatch_industrial.json").read_text(encoding="utf-8"))
industrial_exit = int(os.environ.get("INDUSTRIAL_EXIT", "1"))
mismatch_industrial_exit = int(os.environ.get("MISMATCH_INDUSTRIAL_EXIT", "1"))

summary = {
    "default_decision": default_payload.get("decision"),
    "industrial_decision": industrial_payload.get("decision"),
    "override_decision": override_payload.get("decision"),
    "mismatch_default_decision": mismatch_default_payload.get("decision"),
    "mismatch_industrial_decision": mismatch_industrial_payload.get("decision"),
    "override_applied": bool(override_payload.get("override_applied")),
    "industrial_exit_code": industrial_exit,
    "mismatch_industrial_exit_code": mismatch_industrial_exit,
}
summary["result_flags"] = {
    "default_expected_non_fail": "PASS" if summary["default_decision"] in {"PASS", "NEEDS_REVIEW"} else "FAIL",
    "industrial_expected_fail": "PASS" if summary["industrial_decision"] == "FAIL" and industrial_exit != 0 else "FAIL",
    "override_expected_pass": "PASS" if summary["override_decision"] == "PASS" and summary["override_applied"] else "FAIL",
    "mismatch_default_expected_review": "PASS"
    if summary["mismatch_default_decision"] == "NEEDS_REVIEW"
    else "FAIL",
    "mismatch_industrial_expected_fail": "PASS"
    if summary["mismatch_industrial_decision"] == "FAIL" and mismatch_industrial_exit != 0
    else "FAIL",
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
            f"- override_decision: `{summary['override_decision']}`",
            f"- mismatch_default_decision: `{summary['mismatch_default_decision']}`",
            f"- mismatch_industrial_decision: `{summary['mismatch_industrial_decision']}`",
            f"- override_applied: `{summary['override_applied']}`",
            f"- industrial_exit_code: `{summary['industrial_exit_code']}`",
            f"- mismatch_industrial_exit_code: `{summary['mismatch_industrial_exit_code']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            f"- default_expected_non_fail: `{summary['result_flags']['default_expected_non_fail']}`",
            f"- industrial_expected_fail: `{summary['result_flags']['industrial_expected_fail']}`",
            f"- override_expected_pass: `{summary['result_flags']['override_expected_pass']}`",
            f"- mismatch_default_expected_review: `{summary['result_flags']['mismatch_default_expected_review']}`",
            f"- mismatch_industrial_expected_fail: `{summary['result_flags']['mismatch_industrial_expected_fail']}`",
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
