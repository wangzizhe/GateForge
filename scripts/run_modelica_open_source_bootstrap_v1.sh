#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_MODELICA_BOOTSTRAP_OUT_DIR:-artifacts/modelica_open_source_bootstrap_v1}"
MANIFEST="${GATEFORGE_MODELICA_SOURCE_MANIFEST:-data/modelica_open_source_seed_sources_v1.json}"
CACHE_ROOT="${GATEFORGE_MODELICA_SOURCE_CACHE_ROOT:-assets_private/modelica_sources}"
EXPORT_ROOT="${GATEFORGE_MODELICA_EXPORT_ROOT:-assets_private/modelica/open_source}"
MAX_MODELS_PER_SOURCE="${GATEFORGE_MAX_MODELS_PER_SOURCE:-180}"
FETCH="${GATEFORGE_MODELICA_BOOTSTRAP_FETCH:-1}"

mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md
export OUT_DIR EXPORT_ROOT
export MAX_MODELS_PER_SOURCE

HARVEST_ARGS=(
  --source-manifest "$MANIFEST"
  --source-name "open_source_modelica_bootstrap_v1"
  --source-cache-root "$CACHE_ROOT"
  --export-root "$EXPORT_ROOT"
  --max-models-per-source "$MAX_MODELS_PER_SOURCE"
  --catalog-out "$OUT_DIR/candidate_catalog.json"
  --out "$OUT_DIR/harvest_summary.json"
  --report-out "$OUT_DIR/harvest_summary.md"
)

if [ "$FETCH" = "1" ]; then
  HARVEST_ARGS+=(--execute-fetch)
fi

python3 -m gateforge.dataset_modelica_open_source_harvest_v1 "${HARVEST_ARGS[@]}"

HARVEST_TOTAL="$(python3 - <<'PY'
import json
import os
from pathlib import Path
p = Path(os.environ.get("OUT_DIR", "artifacts/modelica_open_source_bootstrap_v1")) / "harvest_summary.json"
if not p.exists():
    print(0)
else:
    payload = json.loads(p.read_text(encoding="utf-8"))
    print(int(payload.get("total_candidates", 0) or 0))
PY
)"

if [ "$HARVEST_TOTAL" -le 0 ]; then
  python3 - <<'PY'
import json
import os
from pathlib import Path

out = Path(os.environ.get("OUT_DIR", "artifacts/modelica_open_source_bootstrap_v1"))
export_root = os.environ.get("EXPORT_ROOT", "assets_private/modelica/open_source")
summary = {
    "status": "FAIL",
    "harvest_status": "NEEDS_REVIEW",
    "intake_status": "SKIPPED",
    "harvest_total_candidates": 0,
    "accepted_models": 0,
    "rejected_models": 0,
    "export_root": export_root,
    "next_command": "GATEFORGE_MODELICA_BOOTSTRAP_FETCH=1 bash scripts/run_modelica_open_source_bootstrap_v1.sh",
    "alerts": ["harvest_total_candidates_zero", "intake_skipped"],
}
(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps({"status": "FAIL", "accepted_models": 0}))
PY
  cat "$OUT_DIR/summary.json"
  exit 1
fi

python3 -m gateforge.dataset_open_source_model_intake_v1 \
  --candidate-catalog "$OUT_DIR/candidate_catalog.json" \
  --source-name "open_source_modelica_bootstrap_v1" \
  --registry-out "$OUT_DIR/accepted_registry_rows.json" \
  --out "$OUT_DIR/intake_summary.json" \
  --report-out "$OUT_DIR/intake_summary.md"

python3 - <<'PY'
import json
import os
from pathlib import Path

out = Path(os.environ.get("OUT_DIR", "artifacts/modelica_open_source_bootstrap_v1"))
export_root = os.environ.get("EXPORT_ROOT", "assets_private/modelica/open_source")

harvest = json.loads((out / "harvest_summary.json").read_text(encoding="utf-8"))
intake = json.loads((out / "intake_summary.json").read_text(encoding="utf-8"))

accepted = int(intake.get("accepted_count", 0) or 0)
status = "PASS" if accepted > 0 else "NEEDS_REVIEW"
next_cmd = f'GATEFORGE_PRIVATE_MODEL_ROOTS="{export_root}" bash scripts/run_private_model_mutation_scale_sprint_v1.sh'

summary = {
    "status": status,
    "harvest_status": harvest.get("status"),
    "intake_status": intake.get("status"),
    "harvest_total_candidates": harvest.get("total_candidates"),
    "accepted_models": accepted,
    "rejected_models": intake.get("rejected_count"),
    "max_models_per_source": int(os.environ.get("MAX_MODELS_PER_SOURCE", "0") or 0),
    "export_root": export_root,
    "next_command": next_cmd,
}
if accepted == 0:
    summary["alerts"] = ["accepted_models_zero"]

(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# GateForge Modelica Open-Source Bootstrap v1",
            "",
            f"- status: `{summary['status']}`",
            f"- harvest_status: `{summary['harvest_status']}`",
            f"- intake_status: `{summary['intake_status']}`",
            f"- harvest_total_candidates: `{summary['harvest_total_candidates']}`",
            f"- accepted_models: `{summary['accepted_models']}`",
            f"- export_root: `{summary['export_root']}`",
            "",
            "## Next",
            "",
            f"`{summary['next_command']}`",
            "",
        ]
    ),
    encoding="utf-8",
)
print(json.dumps({"status": summary["status"], "accepted_models": summary["accepted_models"]}))
PY

cat "$OUT_DIR/summary.json"
