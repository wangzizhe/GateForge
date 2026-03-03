#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/run_modelica_open_source_bootstrap_v1_demo"
mkdir -p "$OUT_DIR/sources/demo_lib/Plant"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md
rm -rf "$OUT_DIR/exported"

cat > "$OUT_DIR/sources/demo_lib/Plant/Loop.mo" <<'EOF'
model Loop
  Real x;
equation
  der(x) = -0.5 * x;
end Loop;
EOF

cat > "$OUT_DIR/manifest.json" <<JSON
{
  "sources": [
    {
      "source_id": "demo_lib",
      "mode": "local",
      "local_path": "$OUT_DIR/sources/demo_lib",
      "license": "BSD-3-Clause",
      "scale_hint": "medium",
      "package_roots": ["Plant"]
    }
  ]
}
JSON

GATEFORGE_MODELICA_SOURCE_MANIFEST="$OUT_DIR/manifest.json" \
GATEFORGE_MODELICA_BOOTSTRAP_FETCH=0 \
GATEFORGE_MODELICA_BOOTSTRAP_OUT_DIR="$OUT_DIR/bootstrap" \
GATEFORGE_MODELICA_SOURCE_CACHE_ROOT="$OUT_DIR/cache" \
GATEFORGE_MODELICA_EXPORT_ROOT="$OUT_DIR/exported" \
bash scripts/run_modelica_open_source_bootstrap_v1.sh

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/run_modelica_open_source_bootstrap_v1_demo/bootstrap")
payload = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if str(payload.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "accepted_present": "PASS" if int(payload.get("accepted_models", 0) or 0) >= 1 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
summary = {
    "bundle_status": bundle_status,
    "status": payload.get("status"),
    "accepted_models": payload.get("accepted_models"),
    "result_flags": flags,
}
Path("artifacts/run_modelica_open_source_bootstrap_v1_demo/demo_summary.json").write_text(
    json.dumps(summary, indent=2), encoding="utf-8"
)
print(json.dumps({"bundle_status": bundle_status, "accepted_models": summary["accepted_models"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
