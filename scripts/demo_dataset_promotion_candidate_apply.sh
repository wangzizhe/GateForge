#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_promotion_candidate_apply_demo"
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

run_dep_script "scripts/demo_dataset_promotion_candidate.sh" "artifacts/dataset_promotion_candidate_demo/advisor.json"

cat > "$OUT_DIR/advisor_promote.json" <<'JSON'
{
  "generated_at_utc": "2026-02-26T00:00:00Z",
  "sources": {
    "snapshot_path": "synthetic",
    "strategy_apply_history_path": "synthetic",
    "strategy_apply_history_trend_path": "synthetic"
  },
  "advice": {
    "decision": "PROMOTE",
    "action": "promote_candidate",
    "confidence": 0.92,
    "reasons": ["synthetic_promote_for_demo"],
    "dry_run": true
  }
}
JSON

cat > "$OUT_DIR/approval_approve.json" <<'JSON'
{"decision":"approve","reviewer":"human.reviewer"}
JSON

python3 -m gateforge.dataset_promotion_candidate_apply \
  --advisor-summary "$OUT_DIR/advisor_promote.json" \
  --approval "$OUT_DIR/approval_approve.json" \
  --target-state "$OUT_DIR/active_promotion.json" \
  --out "$OUT_DIR/apply_needs_review.json" \
  --report "$OUT_DIR/apply_needs_review.md"

python3 -m gateforge.dataset_promotion_candidate_apply \
  --advisor-summary "$OUT_DIR/advisor_promote.json" \
  --approval "$OUT_DIR/approval_approve.json" \
  --apply \
  --target-state "$OUT_DIR/active_promotion.json" \
  --out "$OUT_DIR/apply_pass.json" \
  --report "$OUT_DIR/apply_pass.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_promotion_candidate_apply_demo")
needs_review = json.loads((out / "apply_needs_review.json").read_text(encoding="utf-8"))
passed = json.loads((out / "apply_pass.json").read_text(encoding="utf-8"))
active = json.loads((out / "active_promotion.json").read_text(encoding="utf-8"))
flags = {
    "needs_review_without_apply_flag": "PASS"
    if needs_review.get("final_status") == "NEEDS_REVIEW"
    else "FAIL",
    "pass_with_apply_flag": "PASS"
    if passed.get("final_status") == "PASS"
    else "FAIL",
    "active_promotion_written": "PASS"
    if isinstance(active.get("active_dataset_promotion_decision"), str) and active.get("active_dataset_promotion_decision")
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "needs_review_status": needs_review.get("final_status"),
    "pass_status": passed.get("final_status"),
    "active_dataset_promotion_decision": active.get("active_dataset_promotion_decision"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Dataset Promotion Candidate Apply Demo",
            "",
            f"- needs_review_status: `{summary['needs_review_status']}`",
            f"- pass_status: `{summary['pass_status']}`",
            f"- active_dataset_promotion_decision: `{summary['active_dataset_promotion_decision']}`",
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

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
