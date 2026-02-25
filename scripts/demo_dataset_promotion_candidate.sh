#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_promotion_candidate_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

bash scripts/demo_dataset_governance_snapshot.sh >/dev/null
bash scripts/demo_dataset_strategy_autotune_apply_history.sh >/dev/null

python3 -m gateforge.dataset_promotion_candidate_advisor \
  --snapshot artifacts/dataset_governance_snapshot_demo/summary.json \
  --strategy-apply-history artifacts/dataset_strategy_autotune_apply_history_demo/history_summary.json \
  --strategy-apply-history-trend artifacts/dataset_strategy_autotune_apply_history_demo/history_trend.json \
  --out "$OUT_DIR/advisor.json" \
  --report-out "$OUT_DIR/advisor.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_promotion_candidate_demo")
advisor = json.loads((out / "advisor.json").read_text(encoding="utf-8"))
advice = advisor.get("advice") or {}
flags = {
    "decision_present": "PASS" if advice.get("decision") in {"PROMOTE", "HOLD", "BLOCK"} else "FAIL",
    "action_present": "PASS" if isinstance(advice.get("action"), str) and advice.get("action") else "FAIL",
    "confidence_present": "PASS" if isinstance(advice.get("confidence"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "decision": advice.get("decision"),
    "action": advice.get("action"),
    "confidence": advice.get("confidence"),
    "reasons_count": len(advice.get("reasons") or []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Dataset Promotion Candidate Demo",
            "",
            f"- decision: `{summary['decision']}`",
            f"- action: `{summary['action']}`",
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
print(json.dumps({"bundle_status": bundle_status, "decision": summary["decision"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
