#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/run_modelica_open_source_growth_sprint_v1_demo"
SRC_DIR="$OUT_DIR/sources"
mkdir -p "$SRC_DIR/demo_repo/Base/A" "$SRC_DIR/demo_repo/Base/B"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md
rm -rf "$OUT_DIR/growth"

cat > "$SRC_DIR/demo_repo/Base/A/A1.mo" <<'EOF'
model A1
  Real x;
equation
  der(x) = -x;
end A1;
EOF

cat > "$SRC_DIR/demo_repo/Base/A/A2.mo" <<'EOF'
model A2
  Real x;
equation
  der(x) = -0.3*x;
end A2;
EOF

cat > "$SRC_DIR/demo_repo/Base/B/B1.mo" <<'EOF'
model B1
  Real x;
equation
  der(x) = -0.2*x;
end B1;
EOF

cat > "$OUT_DIR/manifest.json" <<JSON
{
  "sources": [
    {
      "source_id": "demo_repo",
      "mode": "local",
      "local_path": "$SRC_DIR/demo_repo",
      "license": "BSD-3-Clause",
      "scale_hint": "medium",
      "package_roots": ["Base"]
    }
  ]
}
JSON

GATEFORGE_MODELICA_GROWTH_SPRINT_OUT_DIR="$OUT_DIR/growth" \
GATEFORGE_MODELICA_SOURCE_MANIFEST="$OUT_DIR/manifest.json" \
GATEFORGE_MODELICA_SOURCE_CACHE_ROOT="$OUT_DIR/cache" \
GATEFORGE_MODELICA_EXPORT_ROOT="$OUT_DIR/exported" \
GATEFORGE_MODELICA_BOOTSTRAP_FETCH=0 \
GATEFORGE_MODELICA_BOOTSTRAP_PROFILE=balanced \
GATEFORGE_MAX_MODELS_PER_SOURCE=30 \
GATEFORGE_BOOTSTRAP_MIN_ACCEPTED_MODELS=1 \
GATEFORGE_BOOTSTRAP_MIN_ACCEPTED_LARGE_MODELS=0 \
GATEFORGE_BOOTSTRAP_MIN_ACCEPTED_LARGE_RATIO_PCT=0 \
GATEFORGE_MANIFEST_EXPAND_MAX_SHARDS_PER_SOURCE=4 \
GATEFORGE_MANIFEST_EXPAND_MIN_MO_FILES_PER_SHARD=1 \
GATEFORGE_MIN_DISCOVERED_MODELS=1 \
GATEFORGE_MIN_ACCEPTED_MODELS=1 \
GATEFORGE_MIN_ACCEPTED_LARGE_MODELS=0 \
GATEFORGE_MIN_ACCEPTED_LARGE_RATIO_PCT=0 \
GATEFORGE_MIN_GENERATED_MUTATIONS=6 \
GATEFORGE_MIN_MUTATION_PER_MODEL=1 \
GATEFORGE_MIN_REPRODUCIBLE_MUTATIONS=0 \
GATEFORGE_MUTATIONS_PER_FAILURE_TYPE=2 \
GATEFORGE_FAILURE_TYPES="simulate_error,model_check_error" \
GATEFORGE_TARGET_SCALES="small,medium,large" \
bash scripts/run_modelica_open_source_growth_sprint_v1.sh >/dev/null

python3 - <<'PY'
import json
from pathlib import Path

summary = json.loads(
    (Path("artifacts/run_modelica_open_source_growth_sprint_v1_demo/growth/summary.json")).read_text(encoding="utf-8")
)
flags = {
    "bundle_status_pass": "PASS" if summary.get("bundle_status") == "PASS" else "FAIL",
    "accepted_models_present": "PASS" if int(summary.get("accepted_models", 0) or 0) >= 1 else "FAIL",
    "generated_mutations_present": "PASS" if int(summary.get("generated_mutations", 0) or 0) >= 6 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "bundle_status": bundle_status,
    "scale_gate_status": summary.get("scale_gate_status"),
    "accepted_models": summary.get("accepted_models"),
    "accepted_large_models": summary.get("accepted_large_models"),
    "generated_mutations": summary.get("generated_mutations"),
    "result_flags": flags,
}
Path("artifacts/run_modelica_open_source_growth_sprint_v1_demo/demo_summary.json").write_text(
    json.dumps(payload, indent=2), encoding="utf-8"
)
print(json.dumps({"bundle_status": bundle_status, "accepted_models": payload["accepted_models"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
