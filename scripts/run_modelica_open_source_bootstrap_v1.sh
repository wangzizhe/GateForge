#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_MODELICA_BOOTSTRAP_OUT_DIR:-artifacts/modelica_open_source_bootstrap_v1}"
MANIFEST="${GATEFORGE_MODELICA_SOURCE_MANIFEST:-data/modelica_open_source_seed_sources_v1.json}"
CACHE_ROOT="${GATEFORGE_MODELICA_SOURCE_CACHE_ROOT:-assets_private/modelica_sources}"
EXPORT_ROOT="${GATEFORGE_MODELICA_EXPORT_ROOT:-assets_private/modelica/open_source}"
PROFILE="${GATEFORGE_MODELICA_BOOTSTRAP_PROFILE:-balanced}"
PROFILE="$(echo "$PROFILE" | tr '[:upper:]' '[:lower:]' | xargs)"
if [ -z "$PROFILE" ]; then
  PROFILE="balanced"
fi

DEFAULT_MAX_MODELS_PER_SOURCE="180"
DEFAULT_MIN_ACCEPTED_MODELS="1"
DEFAULT_MIN_ACCEPTED_LARGE_MODELS="0"
DEFAULT_MIN_ACCEPTED_LARGE_RATIO_PCT="0"
if [ "$PROFILE" = "large_first" ]; then
  DEFAULT_MAX_MODELS_PER_SOURCE="260"
  DEFAULT_MIN_ACCEPTED_MODELS="20"
  DEFAULT_MIN_ACCEPTED_LARGE_MODELS="8"
  DEFAULT_MIN_ACCEPTED_LARGE_RATIO_PCT="25"
fi

MAX_MODELS_PER_SOURCE="${GATEFORGE_MAX_MODELS_PER_SOURCE:-$DEFAULT_MAX_MODELS_PER_SOURCE}"
MIN_ACCEPTED_MODELS="${GATEFORGE_BOOTSTRAP_MIN_ACCEPTED_MODELS:-$DEFAULT_MIN_ACCEPTED_MODELS}"
MIN_ACCEPTED_LARGE_MODELS="${GATEFORGE_BOOTSTRAP_MIN_ACCEPTED_LARGE_MODELS:-$DEFAULT_MIN_ACCEPTED_LARGE_MODELS}"
MIN_ACCEPTED_LARGE_RATIO_PCT="${GATEFORGE_BOOTSTRAP_MIN_ACCEPTED_LARGE_RATIO_PCT:-$DEFAULT_MIN_ACCEPTED_LARGE_RATIO_PCT}"
FETCH="${GATEFORGE_MODELICA_BOOTSTRAP_FETCH:-1}"

mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md
export OUT_DIR EXPORT_ROOT
export MAX_MODELS_PER_SOURCE
export PROFILE MIN_ACCEPTED_MODELS MIN_ACCEPTED_LARGE_MODELS MIN_ACCEPTED_LARGE_RATIO_PCT

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
registry = json.loads((out / "accepted_registry_rows.json").read_text(encoding="utf-8"))

accepted = int(intake.get("accepted_count", 0) or 0)
models = registry.get("models") if isinstance(registry.get("models"), list) else []
accepted_large = len([x for x in models if isinstance(x, dict) and str(x.get("suggested_scale") or "").lower() == "large"])
accepted_medium = len([x for x in models if isinstance(x, dict) and str(x.get("suggested_scale") or "").lower() == "medium"])
accepted_large_ratio_pct = round((accepted_large / accepted) * 100.0, 2) if accepted > 0 else 0.0

min_accepted = int(os.environ.get("MIN_ACCEPTED_MODELS", "1") or 1)
min_accepted_large = int(os.environ.get("MIN_ACCEPTED_LARGE_MODELS", "0") or 0)
min_accepted_large_ratio_pct = float(os.environ.get("MIN_ACCEPTED_LARGE_RATIO_PCT", "0") or 0.0)
ratio_gate_enabled = min_accepted_large > 0

alerts = []
if accepted < min_accepted:
    alerts.append("accepted_models_below_target")
if accepted_large < min_accepted_large:
    alerts.append("accepted_large_models_below_target")
if ratio_gate_enabled and accepted_large_ratio_pct < min_accepted_large_ratio_pct:
    alerts.append("accepted_large_ratio_below_target")

quality_gate_status = "PASS" if not alerts else "NEEDS_REVIEW"
status = "PASS" if accepted > 0 and quality_gate_status == "PASS" else "NEEDS_REVIEW"
profile = str(os.environ.get("PROFILE", "balanced") or "balanced")
if profile == "large_first":
    next_cmd = f'GATEFORGE_PRIVATE_MODEL_ROOTS="{export_root}" bash scripts/run_private_model_mutation_largefirst_sprint_v1.sh'
else:
    next_cmd = f'GATEFORGE_PRIVATE_MODEL_ROOTS="{export_root}" bash scripts/run_private_model_mutation_scale_sprint_v1.sh'

summary = {
    "status": status,
    "profile": profile,
    "harvest_status": harvest.get("status"),
    "intake_status": intake.get("status"),
    "quality_gate_status": quality_gate_status,
    "harvest_total_candidates": harvest.get("total_candidates"),
    "accepted_models": accepted,
    "accepted_medium_models": accepted_medium,
    "accepted_large_models": accepted_large,
    "accepted_large_ratio_pct": accepted_large_ratio_pct,
    "rejected_models": intake.get("rejected_count"),
    "max_models_per_source": int(os.environ.get("MAX_MODELS_PER_SOURCE", "0") or 0),
    "min_accepted_models": min_accepted,
    "min_accepted_large_models": min_accepted_large,
    "min_accepted_large_ratio_pct": min_accepted_large_ratio_pct,
    "ratio_gate_enabled": ratio_gate_enabled,
    "export_root": export_root,
    "next_command": next_cmd,
}
if accepted == 0:
    alerts.append("accepted_models_zero")
if alerts:
    summary["alerts"] = alerts

(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# GateForge Modelica Open-Source Bootstrap v1",
            "",
            f"- status: `{summary['status']}`",
            f"- profile: `{summary['profile']}`",
            f"- harvest_status: `{summary['harvest_status']}`",
            f"- intake_status: `{summary['intake_status']}`",
            f"- quality_gate_status: `{summary['quality_gate_status']}`",
            f"- harvest_total_candidates: `{summary['harvest_total_candidates']}`",
            f"- accepted_models: `{summary['accepted_models']}`",
            f"- accepted_large_models: `{summary['accepted_large_models']}`",
            f"- accepted_large_ratio_pct: `{summary['accepted_large_ratio_pct']}`",
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
