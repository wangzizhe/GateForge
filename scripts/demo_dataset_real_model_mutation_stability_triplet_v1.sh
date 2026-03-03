#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_real_model_mutation_stability_triplet_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/history.jsonl

cat > "$OUT_DIR/s1.json" <<'JSON'
{"bundle_status":"PASS","scale_gate_status":"PASS","accepted_models":1000,"accepted_large_models":250,"generated_mutations":18000,"reproducible_mutations":18000,"mutations_per_failure_type":6}
JSON
cat > "$OUT_DIR/s2.json" <<'JSON'
{"bundle_status":"PASS","scale_gate_status":"PASS","accepted_models":995,"accepted_large_models":248,"generated_mutations":17920,"reproducible_mutations":17920,"mutations_per_failure_type":6}
JSON
cat > "$OUT_DIR/s3.json" <<'JSON'
{"bundle_status":"PASS","scale_gate_status":"PASS","accepted_models":1004,"accepted_large_models":252,"generated_mutations":18040,"reproducible_mutations":18040,"mutations_per_failure_type":6}
JSON

cat > "$OUT_DIR/u1.json" <<'JSON'
{"status":"PASS","effective_unique_accepted_models":1000,"duplicate_ratio_pct":0.0}
JSON
cat > "$OUT_DIR/u2.json" <<'JSON'
{"status":"PASS","effective_unique_accepted_models":995,"duplicate_ratio_pct":0.0}
JSON
cat > "$OUT_DIR/u3.json" <<'JSON'
{"status":"PASS","effective_unique_accepted_models":1004,"duplicate_ratio_pct":0.0}
JSON

python3 -m gateforge.dataset_real_model_mutation_stability_triplet_v1 \
  --record-scale-summary "$OUT_DIR/s1.json" \
  --record-scale-summary "$OUT_DIR/s2.json" \
  --record-scale-summary "$OUT_DIR/s3.json" \
  --record-uniqueness-summary "$OUT_DIR/u1.json" \
  --record-uniqueness-summary "$OUT_DIR/u2.json" \
  --record-uniqueness-summary "$OUT_DIR/u3.json" \
  --ledger "$OUT_DIR/history.jsonl" \
  --window-size 3 \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_real_model_mutation_stability_triplet_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "window_size_ok": "PASS" if int(summary.get("window_size", 0) or 0) == 3 else "FAIL",
    "cv_present": "PASS" if isinstance(summary.get("accepted_models_cv_pct"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "bundle_status": bundle_status,
    "status": summary.get("status"),
    "window_size": summary.get("window_size"),
    "accepted_models_cv_pct": summary.get("accepted_models_cv_pct"),
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "status": payload["status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
