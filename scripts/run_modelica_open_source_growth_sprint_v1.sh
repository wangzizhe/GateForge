#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_MODELICA_GROWTH_SPRINT_OUT_DIR:-artifacts/modelica_open_source_growth_sprint_v1}"
SOURCE_MANIFEST="${GATEFORGE_MODELICA_SOURCE_MANIFEST:-data/modelica_open_source_seed_sources_v1.json}"
CACHE_ROOT="${GATEFORGE_MODELICA_SOURCE_CACHE_ROOT:-assets_private/modelica_sources}"
EXPORT_ROOT="${GATEFORGE_MODELICA_EXPORT_ROOT:-assets_private/modelica/open_source}"
BOOTSTRAP_PROFILE="${GATEFORGE_MODELICA_BOOTSTRAP_PROFILE:-large_first}"
export GATEFORGE_MODELICA_GROWTH_SPRINT_OUT_DIR="$OUT_DIR"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md

EXPAND_OUT="$OUT_DIR/manifest_expand"
BOOTSTRAP_OUT="$OUT_DIR/bootstrap"
SCALE_OUT="$OUT_DIR/scale"
mkdir -p "$EXPAND_OUT" "$BOOTSTRAP_OUT" "$SCALE_OUT"

GATEFORGE_MODELICA_MANIFEST_EXPAND_OUT_DIR="$EXPAND_OUT" \
GATEFORGE_MODELICA_SOURCE_MANIFEST="$SOURCE_MANIFEST" \
GATEFORGE_MODELICA_SOURCE_CACHE_ROOT="$CACHE_ROOT" \
bash scripts/run_modelica_open_source_manifest_expand_v1.sh >/dev/null

MANIFEST_FOR_BOOTSTRAP="$SOURCE_MANIFEST"
if [ -f "$EXPAND_OUT/summary.json" ]; then
  export EXPAND_SUMMARY_PATH="$EXPAND_OUT/summary.json"
  ADDED_SOURCES="$(python3 - <<'PY'
import json
import os
from pathlib import Path
p = Path(os.environ.get("EXPAND_SUMMARY_PATH", "artifacts/modelica_open_source_growth_sprint_v1/manifest_expand/summary.json"))
if p.exists():
    payload = json.loads(p.read_text(encoding="utf-8"))
    print(int(payload.get("added_sources_count", 0) or 0))
else:
    print(0)
PY
)"
  if [ "${ADDED_SOURCES:-0}" -gt 0 ] && [ -f "$EXPAND_OUT/expanded_manifest.json" ]; then
    MANIFEST_FOR_BOOTSTRAP="$EXPAND_OUT/expanded_manifest.json"
  fi
fi

GATEFORGE_MODELICA_BOOTSTRAP_OUT_DIR="$BOOTSTRAP_OUT" \
GATEFORGE_MODELICA_SOURCE_MANIFEST="$MANIFEST_FOR_BOOTSTRAP" \
GATEFORGE_MODELICA_SOURCE_CACHE_ROOT="$CACHE_ROOT" \
GATEFORGE_MODELICA_EXPORT_ROOT="$EXPORT_ROOT" \
GATEFORGE_MODELICA_BOOTSTRAP_PROFILE="$BOOTSTRAP_PROFILE" \
bash scripts/run_modelica_open_source_bootstrap_v1.sh >/dev/null

PRIVATE_MODEL_ROOTS="$(python3 - <<'PY'
import json
import os
from pathlib import Path
out = Path(os.environ.get("GATEFORGE_MODELICA_GROWTH_SPRINT_OUT_DIR", "artifacts/modelica_open_source_growth_sprint_v1"))
p = out / "bootstrap" / "summary.json"
if p.exists():
    payload = json.loads(p.read_text(encoding="utf-8"))
    print(str(payload.get("export_root") or "assets_private/modelica/open_source"))
else:
    print("assets_private/modelica/open_source")
PY
)"

GATEFORGE_PRIVATE_BATCH_OUT_DIR="$SCALE_OUT" \
GATEFORGE_PRIVATE_MODEL_ROOTS="$PRIVATE_MODEL_ROOTS" \
bash scripts/run_private_model_mutation_largefirst_sprint_v1.sh >/dev/null

python3 - <<'PY'
import json
import os
from pathlib import Path

out = Path(os.environ.get("GATEFORGE_MODELICA_GROWTH_SPRINT_OUT_DIR", "artifacts/modelica_open_source_growth_sprint_v1"))
expand = json.loads((out / "manifest_expand" / "summary.json").read_text(encoding="utf-8"))
bootstrap = json.loads((out / "bootstrap" / "summary.json").read_text(encoding="utf-8"))
scale = json.loads((out / "scale" / "summary.json").read_text(encoding="utf-8"))

flags = {
    "manifest_expander_status_present": "PASS" if str(expand.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "bootstrap_status_present": "PASS" if str(bootstrap.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "scale_bundle_pass": "PASS" if str(scale.get("bundle_status") or "") == "PASS" else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

summary = {
    "bundle_status": bundle_status,
    "manifest_expand_status": expand.get("status"),
    "manifest_added_sources_count": expand.get("added_sources_count"),
    "bootstrap_status": bootstrap.get("status"),
    "bootstrap_profile": bootstrap.get("profile"),
    "bootstrap_accepted_models": bootstrap.get("accepted_models"),
    "bootstrap_accepted_large_models": bootstrap.get("accepted_large_models"),
    "scale_gate_status": scale.get("scale_gate_status"),
    "accepted_models": scale.get("accepted_models"),
    "accepted_large_models": scale.get("accepted_large_models"),
    "accepted_large_ratio_pct": scale.get("accepted_large_ratio_pct"),
    "generated_mutations": scale.get("generated_mutations"),
    "reproducible_mutations": scale.get("reproducible_mutations"),
    "result_flags": flags,
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# GateForge Modelica Open-Source Growth Sprint v1",
            "",
            f"- bundle_status: `{summary['bundle_status']}`",
            f"- manifest_expand_status: `{summary['manifest_expand_status']}`",
            f"- bootstrap_status: `{summary['bootstrap_status']}`",
            f"- scale_gate_status: `{summary['scale_gate_status']}`",
            f"- accepted_models: `{summary['accepted_models']}`",
            f"- accepted_large_models: `{summary['accepted_large_models']}`",
            f"- generated_mutations: `{summary['generated_mutations']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"bundle_status": bundle_status, "scale_gate_status": summary["scale_gate_status"]}))
if bundle_status != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
