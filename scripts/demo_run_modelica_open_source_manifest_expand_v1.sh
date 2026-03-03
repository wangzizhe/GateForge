#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="artifacts/run_modelica_open_source_manifest_expand_v1_demo"
SRC_DIR="$OUT_DIR/sources"
mkdir -p "$SRC_DIR/demo_repo/Base/A" "$SRC_DIR/demo_repo/Base/B"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

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
  der(x) = -0.1*x;
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

GATEFORGE_MODELICA_SOURCE_MANIFEST="$OUT_DIR/manifest.json" \
GATEFORGE_MODELICA_SOURCE_CACHE_ROOT="$OUT_DIR/cache" \
GATEFORGE_MODELICA_MANIFEST_EXPAND_OUT_DIR="$OUT_DIR/expand" \
GATEFORGE_MANIFEST_EXPAND_MAX_SHARDS_PER_SOURCE=4 \
GATEFORGE_MANIFEST_EXPAND_MIN_MO_FILES_PER_SHARD=1 \
bash scripts/run_modelica_open_source_manifest_expand_v1.sh >/dev/null

python3 - <<'PY'
import json
from pathlib import Path

out = Path("artifacts/run_modelica_open_source_manifest_expand_v1_demo/expand")
summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
flags = {
    "status_present": "PASS" if str(summary.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "added_sources_present": "PASS" if int(summary.get("added_sources_count", 0) or 0) >= 1 else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"
payload = {
    "bundle_status": bundle_status,
    "status": summary.get("status"),
    "base_sources": summary.get("base_sources"),
    "expanded_sources": summary.get("expanded_sources"),
    "added_sources_count": summary.get("added_sources_count"),
    "result_flags": flags,
}
Path("artifacts/run_modelica_open_source_manifest_expand_v1_demo/demo_summary.json").write_text(
    json.dumps(payload, indent=2), encoding="utf-8"
)
print(json.dumps({"bundle_status": bundle_status, "added_sources_count": payload["added_sources_count"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY
