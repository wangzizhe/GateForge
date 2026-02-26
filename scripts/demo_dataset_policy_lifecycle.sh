#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_policy_lifecycle_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

run_dep_script() {
  local script_path="$1"
  local sentinel="$2"
  if [ "${GATEFORGE_DEMO_FAST:-0}" = "1" ] && [ -f "$sentinel" ]; then
    return 0
  fi
  bash "$script_path" >/dev/null
}

run_dep_script "scripts/demo_dataset_governance.sh" "artifacts/dataset_governance_demo/advisor.json"

cp policies/dataset/default.json "$OUT_DIR/policy.copy.json"

python3 -m gateforge.dataset_policy_patch_proposal \
  --advisor-summary artifacts/dataset_governance_demo/advisor.json \
  --policy-path "$OUT_DIR/policy.copy.json" \
  --proposal-id dataset-governance-demo-apply-001 \
  --out "$OUT_DIR/proposal.json" \
  --report "$OUT_DIR/proposal.md"

cat > "$OUT_DIR/approval_approve.json" <<'JSON'
{"decision":"approve","reviewer":"human.reviewer"}
JSON
cat > "$OUT_DIR/approval_reject.json" <<'JSON'
{"decision":"reject","reviewer":"human.reviewer"}
JSON

python3 -m gateforge.dataset_policy_patch_apply \
  --proposal "$OUT_DIR/proposal.json" \
  --approval "$OUT_DIR/approval_approve.json" \
  --apply \
  --out "$OUT_DIR/apply_pass.json" \
  --report "$OUT_DIR/apply_pass.md"

set +e
python3 -m gateforge.dataset_policy_patch_apply \
  --proposal "$OUT_DIR/proposal.json" \
  --approval "$OUT_DIR/approval_reject.json" \
  --out "$OUT_DIR/apply_reject.json" \
  --report "$OUT_DIR/apply_reject.md"
REJECT_RC=$?
set -e

python3 -m gateforge.dataset_governance_ledger \
  --record "$OUT_DIR/apply_pass.json" \
  --record "$OUT_DIR/apply_reject.json" \
  --ledger "$OUT_DIR/ledger.jsonl" \
  --out "$OUT_DIR/ledger_summary.json" \
  --report "$OUT_DIR/ledger_summary.md"

cat > "$OUT_DIR/history_before.json" <<'JSON'
{
  "latest_deduplicated_cases": 10,
  "latest_failure_case_rate": 0.2,
  "freeze_pass_rate": 1.0
}
JSON
cat > "$OUT_DIR/history_after.json" <<'JSON'
{
  "latest_deduplicated_cases": 12,
  "latest_failure_case_rate": 0.26,
  "freeze_pass_rate": 1.0
}
JSON

python3 -m gateforge.dataset_policy_effectiveness \
  --before "$OUT_DIR/history_before.json" \
  --after "$OUT_DIR/history_after.json" \
  --out "$OUT_DIR/effectiveness.json" \
  --report-out "$OUT_DIR/effectiveness.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_policy_lifecycle_demo")
pass_apply = json.loads((out / "apply_pass.json").read_text(encoding="utf-8"))
reject_apply = json.loads((out / "apply_reject.json").read_text(encoding="utf-8"))
ledger = json.loads((out / "ledger_summary.json").read_text(encoding="utf-8"))
eff = json.loads((out / "effectiveness.json").read_text(encoding="utf-8"))

flags = {
    "approve_apply_pass": "PASS" if pass_apply.get("final_status") == "PASS" else "FAIL",
    "reject_apply_fail": "PASS" if reject_apply.get("final_status") == "FAIL" else "FAIL",
    "ledger_records_ok": "PASS" if int(ledger.get("total_records", 0) or 0) >= 2 else "FAIL",
    "effectiveness_decision_present": "PASS" if eff.get("decision") in {"KEEP", "NEEDS_REVIEW", "ROLLBACK_REVIEW"} else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "approve_status": pass_apply.get("final_status"),
    "reject_status": reject_apply.get("final_status"),
    "reject_rc": int(Path("artifacts/dataset_policy_lifecycle_demo/reject.rc").read_text(encoding="utf-8"))
    if Path("artifacts/dataset_policy_lifecycle_demo/reject.rc").exists()
    else None,
    "ledger_total_records": ledger.get("total_records"),
    "effectiveness_decision": eff.get("decision"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Dataset Policy Lifecycle Demo",
            "",
            f"- approve_status: `{summary['approve_status']}`",
            f"- reject_status: `{summary['reject_status']}`",
            f"- ledger_total_records: `{summary['ledger_total_records']}`",
            f"- effectiveness_decision: `{summary['effectiveness_decision']}`",
            f"- bundle_status: `{summary['bundle_status']}`",
            "",
            "## Result Flags",
            "",
            *[f"- {k}: `{v}`" for k, v in sorted(flags.items())],
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

echo "$REJECT_RC" > "$OUT_DIR/reject.rc"
cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
