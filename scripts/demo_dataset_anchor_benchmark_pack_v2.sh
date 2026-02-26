#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_anchor_benchmark_pack_v2_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/baseline_summary.json" <<'JSON'
{"status": "PASS", "baseline_id": "failure_baseline_v1"}
JSON
cat > "$OUT_DIR/quality_gate.json" <<'JSON'
{"status": "PASS", "gate_result": "PASS"}
JSON
cat > "$OUT_DIR/mutation_summary.json" <<'JSON'
{"status": "PASS", "total_mutations": 24, "unique_failure_types": 4}
JSON
cat > "$OUT_DIR/stability_summary.json" <<'JSON'
{"status": "PASS", "stability_ratio_pct": 92.5}
JSON
cat > "$OUT_DIR/ingest_summary.json" <<'JSON'
{"status": "PASS", "ingested_cases": 9}
JSON

python3 -m gateforge.dataset_anchor_benchmark_pack_v2 \
  --failure-baseline-pack-summary "$OUT_DIR/baseline_summary.json" \
  --failure-distribution-quality-gate "$OUT_DIR/quality_gate.json" \
  --mutation-factory-summary "$OUT_DIR/mutation_summary.json" \
  --repro-stability-summary "$OUT_DIR/stability_summary.json" \
  --failure-corpus-ingest-summary "$OUT_DIR/ingest_summary.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/dataset_anchor_benchmark_pack_v2_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "anchor_score_present": "PASS" if isinstance(summary.get("anchor_pack_score"), (int, float)) else "FAIL",
    "steps_present": "PASS" if isinstance(summary.get("reproducible_steps"), list) and len(summary.get("reproducible_steps")) >= 5 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary_out = {
    "anchor_pack_status": summary.get("status"),
    "anchor_ready": summary.get("anchor_ready"),
    "anchor_pack_score": summary.get("anchor_pack_score"),
    "result_flags": flags,
    "bundle_status": bundle_status,
}
(out / "demo_summary.json").write_text(json.dumps(summary_out, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "anchor_pack_status": summary_out["anchor_pack_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
