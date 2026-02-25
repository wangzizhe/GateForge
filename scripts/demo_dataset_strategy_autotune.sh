#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_strategy_autotune_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

bash scripts/demo_dataset_governance_history.sh >/dev/null
bash scripts/demo_dataset_policy_lifecycle.sh >/dev/null

python3 -m gateforge.dataset_strategy_autotune_advisor \
  --dataset-governance-summary artifacts/dataset_policy_lifecycle_demo/ledger_summary.json \
  --dataset-governance-trend artifacts/dataset_governance_history_demo/trend.json \
  --effectiveness-summary artifacts/dataset_policy_lifecycle_demo/effectiveness.json \
  --out "$OUT_DIR/advisor.json" \
  --report-out "$OUT_DIR/advisor.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_strategy_autotune_demo")
advisor = json.loads((out / "advisor.json").read_text(encoding="utf-8"))
advice = advisor.get("advice") if isinstance(advisor.get("advice"), dict) else {}
flags = {
    "suggested_policy_profile_present": "PASS" if isinstance(advice.get("suggested_policy_profile"), str) else "FAIL",
    "suggested_action_present": "PASS" if isinstance(advice.get("suggested_action"), str) else "FAIL",
    "reasons_present": "PASS" if len(advice.get("reasons") or []) >= 1 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "suggested_policy_profile": advice.get("suggested_policy_profile"),
    "suggested_action": advice.get("suggested_action"),
    "confidence": advice.get("confidence"),
    "reasons_count": len(advice.get("reasons") or []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Dataset Strategy Auto-Tune Demo",
            "",
            f"- suggested_policy_profile: `{summary['suggested_policy_profile']}`",
            f"- suggested_action: `{summary['suggested_action']}`",
            f"- confidence: `{summary['confidence']}`",
            f"- reasons_count: `{summary['reasons_count']}`",
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
print(json.dumps({"bundle_status": bundle_status, "suggested_action": summary["suggested_action"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"

