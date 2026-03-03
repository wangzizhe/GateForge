#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/dataset_real_model_uniqueness_guard_v1_demo"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

cat > "$OUT_DIR/m1.mo" <<'EOF'
model M1
  Real x;
equation
  der(x) = -x;
end M1;
EOF

cp "$OUT_DIR/m1.mo" "$OUT_DIR/m1_copy.mo"

cat > "$OUT_DIR/m2.mo" <<'EOF'
model M2
  Real y;
equation
  der(y) = -0.2 * y;
end M2;
EOF

cat > "$OUT_DIR/accepted.json" <<JSON
{
  "rows": [
    {"candidate_id":"m1","model_path":"$OUT_DIR/m1.mo","source_url":"https://x/m1","expected_scale":"large"},
    {"candidate_id":"m1c","model_path":"$OUT_DIR/m1_copy.mo","source_url":"https://x/m1c","expected_scale":"large"},
    {"candidate_id":"m2","model_path":"$OUT_DIR/m2.mo","source_url":"https://x/m2","expected_scale":"medium"}
  ]
}
JSON

cat > "$OUT_DIR/registry.json" <<JSON
{
  "models": [
    {"model_id":"m1","asset_type":"model_source","source_name":"s1","source_path":"$OUT_DIR/m1.mo","suggested_scale":"large"},
    {"model_id":"m1c","asset_type":"model_source","source_name":"s2","source_path":"$OUT_DIR/m1_copy.mo","suggested_scale":"large"},
    {"model_id":"m2","asset_type":"model_source","source_name":"s1","source_path":"$OUT_DIR/m2.mo","suggested_scale":"medium"}
  ]
}
JSON

python3 -m gateforge.dataset_real_model_uniqueness_guard_v1 \
  --intake-runner-accepted "$OUT_DIR/accepted.json" \
  --intake-registry-rows "$OUT_DIR/registry.json" \
  --out "$OUT_DIR/summary.json" \
  --report-out "$OUT_DIR/summary.md"

python3 - <<'PY'
import json
from pathlib import Path
out = Path("artifacts/dataset_real_model_uniqueness_guard_v1_demo")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if summary.get("status") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "duplicate_detected": "PASS" if int(summary.get("duplicate_count", 0) or 0) >= 1 else "FAIL",
    "unique_ratio_present": "PASS" if isinstance(summary.get("unique_checksum_ratio_pct"), (int, float)) else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "bundle_status": bundle_status,
    "status": summary.get("status"),
    "duplicate_count": summary.get("duplicate_count"),
    "unique_checksum_ratio_pct": summary.get("unique_checksum_ratio_pct"),
    "result_flags": flags,
}
(out / "demo_summary.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(json.dumps({"bundle_status": bundle_status, "status": payload["status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
