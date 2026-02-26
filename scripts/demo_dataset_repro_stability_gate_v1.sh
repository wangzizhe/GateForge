#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_repro_stability_gate_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/mutation_manifest.json" <<'JSON'
{
  "schema_version": "mutation_manifest_v1",
  "mutations": [
    {"mutation_id": "mut_001"},
    {"mutation_id": "mut_002"},
    {"mutation_id": "mut_003"}
  ]
}
JSON

cat > "$OUT_DIR/replay_observations.json" <<'JSON'
{
  "observations": [
    {"mutation_id": "mut_001", "observed_failure_types": ["simulate_error", "simulate_error", "simulate_error"]},
    {"mutation_id": "mut_002", "observed_failure_types": ["model_check_error", "model_check_error", "model_check_error"]},
    {"mutation_id": "mut_003", "observed_failure_types": ["semantic_regression", "simulate_error", "semantic_regression"]}
  ]
}
JSON

python3 -m gateforge.dataset_repro_stability_gate_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --replay-observations "$OUT_DIR/replay_observations.json" \
  --min-runs-per-mutation 3 \
  --min-majority-ratio 0.66 \
  --min-stability-ratio-pct 80 \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_repro_stability_gate_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "checked_present": "PASS" if int(summary.get("total_checked_cases", 0) or 0) >= 1 else "FAIL",
    "ratio_present": "PASS" if isinstance(summary.get("stability_ratio_pct"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary_out = {
    "stability_gate_status": summary.get("status"),
    "total_checked_cases": summary.get("total_checked_cases"),
    "stability_ratio_pct": summary.get("stability_ratio_pct"),
    "unstable_cases": summary.get("unstable_cases"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "stability_gate_status": summary_out["stability_gate_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
