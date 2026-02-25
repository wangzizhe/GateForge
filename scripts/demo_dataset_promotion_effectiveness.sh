#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_promotion_effectiveness_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

bash scripts/demo_dataset_promotion_candidate_apply_history.sh >/dev/null

cat > "$OUT_DIR/before.json" <<'JSON'
{
  "pass_rate": 0.6,
  "needs_review_rate": 0.3,
  "fail_rate": 0.1
}
JSON

cp artifacts/dataset_promotion_candidate_apply_history_demo/history_summary.json "$OUT_DIR/after.json"

python3 -m gateforge.dataset_promotion_effectiveness \
  --before "$OUT_DIR/before.json" \
  --after "$OUT_DIR/after.json" \
  --out "$OUT_DIR/effectiveness.json" \
  --report-out "$OUT_DIR/effectiveness.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_promotion_effectiveness_demo")
eff = json.loads((out / "effectiveness.json").read_text(encoding="utf-8"))
flags = {
    "decision_present": "PASS" if eff.get("decision") in {"KEEP", "NEEDS_REVIEW", "ROLLBACK_REVIEW"} else "FAIL",
    "delta_present": "PASS" if isinstance(eff.get("delta"), dict) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "effectiveness_decision": eff.get("decision"),
    "reasons_count": len(eff.get("reasons") or []),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Dataset Promotion Effectiveness Demo",
            "",
            f"- effectiveness_decision: `{summary['effectiveness_decision']}`",
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
print(json.dumps({"bundle_status": bundle_status, "decision": summary["effectiveness_decision"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
cat "$OUT_DIR/summary.md"
