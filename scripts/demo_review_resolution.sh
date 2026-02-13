#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
POLICY_PROFILE="${POLICY_PROFILE:-}"

mkdir -p artifacts/review_demo

cat > artifacts/review_demo/review_context_mid.json <<'EOF'
{
  "risk_level": "low",
  "change_summary": "review resolution demo: medium confidence requires human review",
  "change_plan_confidence": 0.5
}
EOF

AP_CMD=(
  python3 -m gateforge.autopilot
  --goal "apply deterministic patch and run"
  --planner-backend rule
  --materialize-change-set
  --context-json artifacts/review_demo/review_context_mid.json
  --proposal-id review-demo-001
  --baseline baselines/mock_minimal_probe_baseline.json
  --save-run-under autopilot
  --out artifacts/review_demo/source_needs_review.json
)
if [[ -n "$POLICY_PROFILE" ]]; then
  AP_CMD+=(--policy-profile "$POLICY_PROFILE")
fi
"${AP_CMD[@]}"

python3 - <<'PY'
import json
from pathlib import Path
source = json.loads(Path("artifacts/review_demo/source_needs_review.json").read_text(encoding="utf-8"))
if source.get("status") != "NEEDS_REVIEW":
    raise SystemExit("expected NEEDS_REVIEW source status")
PY

cat > artifacts/review_demo/review_approve.json <<'EOF'
{
  "schema_version": "0.1.0",
  "review_id": "review-demo-approve-001",
  "proposal_id": "review-demo-001",
  "reviewer": "human.reviewer",
  "second_reviewer": "human.reviewer.2",
  "second_decision": "approve",
  "decision": "approve",
  "rationale": "All required checks completed and risk accepted.",
  "requested_at_utc": "2026-02-13T09:00:00Z",
  "reviewed_at_utc": "2026-02-13T09:20:00Z",
  "all_required_checks_completed": true,
  "confirmed_checks": [
    "Checked required_human_checks list and evidence artifacts"
  ]
}
EOF

cat > artifacts/review_demo/review_reject.json <<'EOF'
{
  "schema_version": "0.1.0",
  "review_id": "review-demo-reject-001",
  "proposal_id": "review-demo-001",
  "reviewer": "human.reviewer",
  "decision": "reject",
  "rationale": "Risk not acceptable at this time.",
  "requested_at_utc": "2026-02-13T09:00:00Z",
  "reviewed_at_utc": "2026-02-14T12:00:00Z",
  "all_required_checks_completed": true,
  "confirmed_checks": [
    "Checked required_human_checks list and evidence artifacts"
  ]
}
EOF

python3 -m gateforge.review_resolve \
  --summary artifacts/review_demo/source_needs_review.json \
  --review artifacts/review_demo/review_approve.json \
  --out artifacts/review_demo/final_approve.json

set +e
python3 -m gateforge.review_resolve \
  --summary artifacts/review_demo/source_needs_review.json \
  --review artifacts/review_demo/review_reject.json \
  --out artifacts/review_demo/final_reject.json
RC=$?
set -e
if [[ "$RC" -ne 1 ]]; then
  echo "expected reject resolution to exit 1, got $RC" >&2
  exit 1
fi

python3 - <<'PY'
import json
from pathlib import Path

src = json.loads(Path("artifacts/review_demo/source_needs_review.json").read_text(encoding="utf-8"))
approve = json.loads(Path("artifacts/review_demo/final_approve.json").read_text(encoding="utf-8"))
reject = json.loads(Path("artifacts/review_demo/final_reject.json").read_text(encoding="utf-8"))

summary = {
    "source_status": src.get("status"),
    "approve_final_status": approve.get("final_status"),
    "reject_final_status": reject.get("final_status"),
}
summary["result_flags"] = {
    "source_expected_needs_review": "PASS" if summary["source_status"] == "NEEDS_REVIEW" else "FAIL",
    "approve_expected_pass": "PASS" if summary["approve_final_status"] == "PASS" else "FAIL",
    "reject_expected_fail": "PASS" if summary["reject_final_status"] == "FAIL" else "FAIL",
}
summary["bundle_status"] = "PASS" if all(v == "PASS" for v in summary["result_flags"].values()) else "FAIL"

Path("artifacts/review_demo/summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
lines = [
    "# Human Review Resolution Demo",
    "",
    f"- source_status: `{summary['source_status']}`",
    f"- approve_final_status: `{summary['approve_final_status']}`",
    f"- reject_final_status: `{summary['reject_final_status']}`",
    f"- bundle_status: `{summary['bundle_status']}`",
    "",
    "## Result Flags",
    "",
    f"- source_expected_needs_review: `{summary['result_flags']['source_expected_needs_review']}`",
    f"- approve_expected_pass: `{summary['result_flags']['approve_expected_pass']}`",
    f"- reject_expected_fail: `{summary['result_flags']['reject_expected_fail']}`",
]
Path("artifacts/review_demo/summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(json.dumps({"bundle_status": summary["bundle_status"]}))
PY

cat artifacts/review_demo/summary.json
cat artifacts/review_demo/summary.md

python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path("artifacts/review_demo/summary.json").read_text(encoding="utf-8"))
if payload.get("bundle_status") != "PASS":
    raise SystemExit(1)
PY
