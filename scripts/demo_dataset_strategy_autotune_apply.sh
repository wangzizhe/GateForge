#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_strategy_autotune_apply_demo"
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

run_dep_script "scripts/demo_dataset_strategy_autotune.sh" "artifacts/dataset_strategy_autotune_demo/advisor.json"

cat > "$OUT_DIR/approval_approve.json" <<'JSON'
{"decision":"approve","reviewer":"human.reviewer"}
JSON

python3 -m gateforge.dataset_strategy_autotune_apply \
  --advisor-summary artifacts/dataset_strategy_autotune_demo/advisor.json \
  --approval "$OUT_DIR/approval_approve.json" \
  --target-state "$OUT_DIR/active_strategy.json" \
  --out "$OUT_DIR/apply_needs_review.json" \
  --report "$OUT_DIR/apply_needs_review.md"

python3 -m gateforge.dataset_strategy_autotune_apply \
  --advisor-summary artifacts/dataset_strategy_autotune_demo/advisor.json \
  --approval "$OUT_DIR/approval_approve.json" \
  --apply \
  --target-state "$OUT_DIR/active_strategy.json" \
  --out "$OUT_DIR/apply_pass.json" \
  --report "$OUT_DIR/apply_pass.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_strategy_autotune_apply_demo")
needs_review = json.loads((out / "apply_needs_review.json").read_text(encoding="utf-8"))
passed = json.loads((out / "apply_pass.json").read_text(encoding="utf-8"))
active = json.loads((out / "active_strategy.json").read_text(encoding="utf-8"))
flags = {
    "needs_review_without_apply_flag": "PASS"
    if needs_review.get("final_status") == "NEEDS_REVIEW"
    else "FAIL",
    "pass_with_apply_flag": "PASS"
    if passed.get("final_status") == "PASS"
    else "FAIL",
    "active_strategy_written": "PASS"
    if isinstance(active.get("active_dataset_strategy_profile"), str) and active.get("active_dataset_strategy_profile")
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "needs_review_status": needs_review.get("final_status"),
    "pass_status": passed.get("final_status"),
    "active_dataset_strategy_profile": active.get("active_dataset_strategy_profile"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# Dataset Strategy Auto-Tune Apply Demo",
            "",
            f"- needs_review_status: `{summary['needs_review_status']}`",
            f"- pass_status: `{summary['pass_status']}`",
            f"- active_dataset_strategy_profile: `{summary['active_dataset_strategy_profile']}`",
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
