#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_mutation_depth_upgrade_report_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/baseline.json" <<'JSON'
{"generated_mutations":3780,"reproducible_mutations":3780,"mutations_per_failure_type":2}
JSON

cat > "$OUT_DIR/current.json" <<'JSON'
{"generated_mutations":7560,"reproducible_mutations":7560,"mutations_per_failure_type":4,"accepted_models":606}
JSON

python3 -m gateforge.dataset_mutation_depth_upgrade_report_v1 \
  --current-scale-summary "$OUT_DIR/current.json" \
  --baseline-scale-summary "$OUT_DIR/baseline.json" \
  --target-mutations-per-failure-type 4 \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_mutation_depth_upgrade_report_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "depth_reached": "PASS" if int(summary.get("current_mutations_per_failure_type", 0) or 0) >= 4 else "FAIL",
    "multiplier_present": "PASS" if isinstance(summary.get("generated_mutation_multiplier"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "bundle_status": bundle_status,
    "status": summary.get("status"),
    "upgrade_status": summary.get("upgrade_status"),
    "generated_mutation_multiplier": summary.get("generated_mutation_multiplier"),
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "upgrade_status": payload["upgrade_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
