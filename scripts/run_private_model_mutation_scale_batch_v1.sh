#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_PRIVATE_BATCH_OUT_DIR:-artifacts/private_model_mutation_scale_batch_v1}"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl
export OUT_DIR

PROFILE="${GATEFORGE_MODEL_SCALE_PROFILE:-balanced}"
PROFILE="$(echo "$PROFILE" | tr '[:upper:]' '[:lower:]' | xargs)"
if [ -z "$PROFILE" ]; then
  PROFILE="balanced"
fi

DEFAULT_TARGET_SCALES="medium,large"
DEFAULT_MIN_MEDIUM_COMPLEXITY_SCORE="80"
DEFAULT_MIN_LARGE_COMPLEXITY_SCORE="140"
DEFAULT_MIN_ACCEPTED_LARGE_RATIO_PCT="10"
DEFAULT_MAX_MUTATION_MODELS="800"

if [ "$PROFILE" = "large_first" ]; then
  DEFAULT_TARGET_SCALES="large,medium"
  DEFAULT_MIN_MEDIUM_COMPLEXITY_SCORE="70"
  DEFAULT_MIN_LARGE_COMPLEXITY_SCORE="120"
  DEFAULT_MIN_ACCEPTED_LARGE_RATIO_PCT="30"
  DEFAULT_MAX_MUTATION_MODELS="1200"
fi

TARGET_SCALES="${GATEFORGE_TARGET_SCALES:-$DEFAULT_TARGET_SCALES}"
DISCOVERY_MIN_MEDIUM_COMPLEXITY_SCORE="${GATEFORGE_DISCOVERY_MIN_MEDIUM_COMPLEXITY_SCORE:-$DEFAULT_MIN_MEDIUM_COMPLEXITY_SCORE}"
DISCOVERY_MIN_LARGE_COMPLEXITY_SCORE="${GATEFORGE_DISCOVERY_MIN_LARGE_COMPLEXITY_SCORE:-$DEFAULT_MIN_LARGE_COMPLEXITY_SCORE}"
MIN_ACCEPTED_LARGE_RATIO_PCT="${GATEFORGE_MIN_ACCEPTED_LARGE_RATIO_PCT:-$DEFAULT_MIN_ACCEPTED_LARGE_RATIO_PCT}"
MAX_MUTATION_MODELS="${GATEFORGE_MAX_MUTATION_MODELS:-$DEFAULT_MAX_MUTATION_MODELS}"
FAILURE_TYPES="${GATEFORGE_FAILURE_TYPES:-simulate_error,model_check_error,semantic_regression,numerical_instability,constraint_violation}"
export TARGET_SCALES
export FAILURE_TYPES
export PROFILE
export DISCOVERY_MIN_MEDIUM_COMPLEXITY_SCORE
export DISCOVERY_MIN_LARGE_COMPLEXITY_SCORE
export MIN_ACCEPTED_LARGE_RATIO_PCT
export MAX_MUTATION_MODELS

python3 - <<'PY'
import json
import os
from pathlib import Path

out = Path(os.environ["OUT_DIR"])
payload = {
    "model_scale_profile": os.environ.get("PROFILE", "balanced"),
    "target_scales": [x.strip() for x in os.environ.get("TARGET_SCALES", "").split(",") if x.strip()],
    "min_medium_complexity_score": int(os.environ.get("DISCOVERY_MIN_MEDIUM_COMPLEXITY_SCORE", "80") or 80),
    "min_large_complexity_score": int(os.environ.get("DISCOVERY_MIN_LARGE_COMPLEXITY_SCORE", "140") or 140),
    "min_accepted_large_ratio_pct": float(os.environ.get("MIN_ACCEPTED_LARGE_RATIO_PCT", "0") or 0.0),
    "max_mutation_models": int(os.environ.get("MAX_MUTATION_MODELS", "0") or 0),
}
(out / "profile_config.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

ROOTS_RAW="${GATEFORGE_PRIVATE_MODEL_ROOTS:-assets_private/modelica:examples_private/modelica:data/private_modelica}"
ROOTS_CSV="${ROOTS_RAW//:/,}"
IFS=',' read -r -a ROOTS <<< "$ROOTS_CSV"

DISCOVERY_ARGS=()
EXISTING_ROOTS=()
for r in "${ROOTS[@]}"; do
  rr="$(echo "$r" | xargs)"
  if [ -n "$rr" ]; then
    DISCOVERY_ARGS+=(--model-root "$rr")
    if [ -d "$rr" ]; then
      EXISTING_ROOTS+=("$rr")
    fi
  fi
done

if [ "${#EXISTING_ROOTS[@]}" -eq 0 ]; then
  echo "{\"status\":\"FAIL\",\"reason\":\"private_model_roots_missing\",\"roots\":\"$ROOTS_RAW\"}" >&2
  exit 1
fi

MODEL_FILE_COUNT=0
for rr in "${EXISTING_ROOTS[@]}"; do
  count="$(find "$rr" -type f -name '*.mo' 2>/dev/null | wc -l | xargs)"
  MODEL_FILE_COUNT=$((MODEL_FILE_COUNT + count))
done

if [ "$MODEL_FILE_COUNT" -le 0 ]; then
  echo "{\"status\":\"FAIL\",\"reason\":\"private_model_files_missing\",\"roots\":\"$ROOTS_RAW\"}" >&2
  exit 1
fi

python3 -m gateforge.dataset_real_model_asset_discovery_v1 \
  "${DISCOVERY_ARGS[@]}" \
  --source-name "private_modelica_asset_pool" \
  --source-domain "physical_ai" \
  --source-url-prefix "local://" \
  --source-repo "private" \
  --source-commit "workspace" \
  --license-tag "Apache-2.0" \
  --min-medium-complexity-score "$DISCOVERY_MIN_MEDIUM_COMPLEXITY_SCORE" \
  --min-large-complexity-score "$DISCOVERY_MIN_LARGE_COMPLEXITY_SCORE" \
  --catalog-out "$OUT_DIR/candidate_catalog.json" \
  --out "$OUT_DIR/asset_discovery_summary.json" \
  --report-out "$OUT_DIR/asset_discovery_summary.md"

# Convert catalog -> intake queue jsonl expected by intake runner.
python3 - <<'PY'
import json
import os
from pathlib import Path

out = Path(os.environ["OUT_DIR"])
cat = json.loads((out / "candidate_catalog.json").read_text(encoding="utf-8"))
rows = cat.get("candidates") if isinstance(cat.get("candidates"), list) else []
q = out / "intake_queue.jsonl"
with q.open("w", encoding="utf-8") as f:
    for row in rows:
        if not isinstance(row, dict):
            continue
        payload = {
            "candidate_id": row.get("candidate_id") or row.get("model_id"),
            "source_url": row.get("source_url"),
            "domain": row.get("domain") or "physical_ai",
            "version_hint": row.get("version_hint") or "workspace",
            "license": row.get("license") or "Apache-2.0",
            "expected_scale": row.get("expected_scale") or row.get("scale_hint") or "small",
            "model_path": row.get("local_path") or row.get("source_path"),
        }
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
PY

python3 -m gateforge.dataset_real_model_intake_pipeline_v1 \
  --candidate-catalog "$OUT_DIR/candidate_catalog.json" \
  --source-name "private_modelica_asset_pool" \
  --probe-mode "syntax" \
  --registry-rows-out "$OUT_DIR/intake_registry_rows.json" \
  --ledger-out "$OUT_DIR/intake_pipeline_ledger.json" \
  --out "$OUT_DIR/intake_pipeline_summary.json" \
  --report-out "$OUT_DIR/intake_pipeline_summary.md"

python3 -m gateforge.dataset_real_model_intake_runner_v1 \
  --intake-queue-jsonl "$OUT_DIR/intake_queue.jsonl" \
  --min-weekly-accepted "${GATEFORGE_MIN_ACCEPTED_MODELS:-4}" \
  --min-weekly-large-accepted "${GATEFORGE_MIN_ACCEPTED_LARGE_MODELS:-1}" \
  --accepted-out "$OUT_DIR/intake_runner_accepted.json" \
  --rejected-out "$OUT_DIR/intake_runner_rejected.json" \
  --out "$OUT_DIR/intake_runner_summary.json" \
  --report-out "$OUT_DIR/intake_runner_summary.md"

# Auto-scale mutation density based on accepted medium/large models and min-generated target.
python3 - <<'PY'
import json
import math
import os
from pathlib import Path

out = Path(os.environ["OUT_DIR"])
registry = json.loads((out / "intake_registry_rows.json").read_text(encoding="utf-8"))
rows = registry.get("models") if isinstance(registry.get("models"), list) else []

target_scales = {x.strip().lower() for x in os.environ.get("TARGET_SCALES", "medium,large").split(",") if x.strip()}
failure_types = [x.strip() for x in os.environ.get("FAILURE_TYPES", "").split(",") if x.strip()]

selected_models = [
    x
    for x in rows
    if isinstance(x, dict) and str(x.get("asset_type") or "") == "model_source" and str(x.get("suggested_scale") or "").lower() in target_scales
]
selected_models.sort(
    key=lambda x: (
        0 if str(x.get("suggested_scale") or "").lower() == "large" else 1,
        str(x.get("model_id") or ""),
    )
)
total_selected_models = len(selected_models)
max_mutation_models = max(0, int(os.environ.get("MAX_MUTATION_MODELS", "0") or 0))
if max_mutation_models > 0:
    selected_models = selected_models[:max_mutation_models]

base_per_type = max(1, int(os.environ.get("GATEFORGE_MUTATIONS_PER_FAILURE_TYPE", "2") or 2))
min_generated = max(0, int(os.environ.get("GATEFORGE_MIN_GENERATED_MUTATIONS", "24") or 24))

if selected_models and failure_types:
    required = int(math.ceil(min_generated / (len(selected_models) * len(failure_types))))
else:
    required = base_per_type

auto_per_type = max(base_per_type, required)

(out / "auto_mutation_scale.json").write_text(
    json.dumps(
        {
            "selected_mutation_models": len(selected_models),
            "selected_mutation_models_total": total_selected_models,
            "max_mutation_models": max_mutation_models,
            "failure_types_count": len(failure_types),
            "base_mutations_per_failure_type": base_per_type,
            "required_mutations_per_failure_type": required,
            "auto_mutations_per_failure_type": auto_per_type,
            "target_scales": sorted(target_scales),
        },
        indent=2,
    ),
    encoding="utf-8",
)
(out / "auto_mutation_scale.env").write_text(
    "\n".join(
        [
            f"AUTO_MUTATIONS_PER_FAILURE_TYPE={auto_per_type}",
            f"SELECTED_MUTATION_MODELS={len(selected_models)}",
            f"SELECTED_MUTATION_MODELS_TOTAL={total_selected_models}",
            f"MAX_MUTATION_MODELS={max_mutation_models}",
            f"FAILURE_TYPE_COUNT={len(failure_types)}",
        ]
    )
    + "\n",
    encoding="utf-8",
)
PY

source "$OUT_DIR/auto_mutation_scale.env"

python3 -m gateforge.dataset_mutation_bulk_pack_builder_v1 \
  --model-registry "$OUT_DIR/intake_registry_rows.json" \
  --target-scales "$TARGET_SCALES" \
  --failure-types "$FAILURE_TYPES" \
  --mutations-per-failure-type "${AUTO_MUTATIONS_PER_FAILURE_TYPE}" \
  --max-models "${MAX_MUTATION_MODELS}" \
  --manifest-out "$OUT_DIR/mutation_manifest.json" \
  --out "$OUT_DIR/mutation_pack_summary.json" \
  --report-out "$OUT_DIR/mutation_pack_summary.md"

python3 -m gateforge.dataset_mutation_real_runner_v1 \
  --validated-mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --timeout-seconds "${GATEFORGE_MUTATION_TIMEOUT_SECONDS:-15}" \
  --max-retries "0" \
  --raw-observations-out "$OUT_DIR/mutation_raw_observations.json" \
  --out "$OUT_DIR/mutation_real_runner_summary.json" \
  --report-out "$OUT_DIR/mutation_real_runner_summary.md"

python3 -m gateforge.dataset_real_model_mutation_scale_gate_v1 \
  --asset-discovery-summary "$OUT_DIR/asset_discovery_summary.json" \
  --intake-pipeline-summary "$OUT_DIR/intake_pipeline_summary.json" \
  --intake-runner-summary "$OUT_DIR/intake_runner_summary.json" \
  --mutation-pack-summary "$OUT_DIR/mutation_pack_summary.json" \
  --mutation-real-runner-summary "$OUT_DIR/mutation_real_runner_summary.json" \
  --min-discovered-models "${GATEFORGE_MIN_DISCOVERED_MODELS:-6}" \
  --min-accepted-models "${GATEFORGE_MIN_ACCEPTED_MODELS:-4}" \
  --min-accepted-large-models "${GATEFORGE_MIN_ACCEPTED_LARGE_MODELS:-1}" \
  --min-generated-mutations "${GATEFORGE_MIN_GENERATED_MUTATIONS:-24}" \
  --min-mutation-per-accepted-model "${GATEFORGE_MIN_MUTATION_PER_MODEL:-4}" \
  --min-reproducible-mutations "${GATEFORGE_MIN_REPRODUCIBLE_MUTATIONS:-0}" \
  --out "$OUT_DIR/scale_gate_summary.json" \
  --report-out "$OUT_DIR/scale_gate_summary.md"

python3 - <<'PY'
import json
import os
from pathlib import Path

out = Path(os.environ["OUT_DIR"])

def _load(name: str) -> dict:
    return json.loads((out / name).read_text(encoding="utf-8"))

discovery = _load("asset_discovery_summary.json")
pipeline = _load("intake_pipeline_summary.json")
runner = _load("intake_runner_summary.json")
pack = _load("mutation_pack_summary.json")
realrun = _load("mutation_real_runner_summary.json")
gate = _load("scale_gate_summary.json")
auto_scale = _load("auto_mutation_scale.json")
profile = _load("profile_config.json")

accepted_models = int(runner.get("accepted_count", 0) or 0)
accepted_large_models = int(runner.get("accepted_large_count", 0) or 0)
accepted_large_ratio_pct = round((accepted_large_models / accepted_models) * 100.0, 2) if accepted_models > 0 else 0.0
min_accepted_large_ratio_pct = float(profile.get("min_accepted_large_ratio_pct", 0.0) or 0.0)
min_accepted_large_models = int(os.environ.get("GATEFORGE_MIN_ACCEPTED_LARGE_MODELS", "1") or 1)
ratio_gate_enabled = min_accepted_large_models > 0

flags = {
    "discovery_exists": "PASS" if int(discovery.get("total_candidates", 0)) >= 0 else "FAIL",
    "pipeline_exists": "PASS" if int(pipeline.get("total_candidates", 0)) >= 0 else "FAIL",
    "runner_exists": "PASS" if int(runner.get("total_candidates", 0)) >= 0 else "FAIL",
    "pack_exists": "PASS" if int(pack.get("total_mutations", 0)) >= 0 else "FAIL",
    "realrun_exists": "PASS" if int(realrun.get("total_mutations", 0)) >= 0 else "FAIL",
    "gate_status_present": "PASS" if str(gate.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "accepted_large_ratio_gate": "PASS"
    if (not ratio_gate_enabled or accepted_large_ratio_pct >= min_accepted_large_ratio_pct)
    else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

summary = {
    "bundle_status": bundle_status,
    "model_scale_profile": profile.get("model_scale_profile"),
    "scale_gate_status": gate.get("status"),
    "discovered_models": discovery.get("total_candidates"),
    "accepted_models": accepted_models,
    "accepted_large_models": accepted_large_models,
    "accepted_large_ratio_pct": accepted_large_ratio_pct,
    "min_accepted_large_ratio_pct": min_accepted_large_ratio_pct,
    "ratio_gate_enabled": ratio_gate_enabled,
    "generated_mutations": pack.get("total_mutations"),
    "reproducible_mutations": realrun.get("executed_count"),
    "target_scales": auto_scale.get("target_scales"),
    "selected_mutation_models": auto_scale.get("selected_mutation_models"),
    "selected_mutation_models_total": auto_scale.get("selected_mutation_models_total"),
    "max_mutation_models": auto_scale.get("max_mutation_models"),
    "failure_types_count": auto_scale.get("failure_types_count"),
    "mutations_per_failure_type": auto_scale.get("auto_mutations_per_failure_type"),
    "result_flags": flags,
}

(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# GateForge Private Model + Mutation Scale Batch v1",
            "",
            f"- bundle_status: `{summary['bundle_status']}`",
            f"- model_scale_profile: `{summary['model_scale_profile']}`",
            f"- scale_gate_status: `{summary['scale_gate_status']}`",
            f"- discovered_models: `{summary['discovered_models']}`",
            f"- accepted_models: `{summary['accepted_models']}`",
            f"- accepted_large_models: `{summary['accepted_large_models']}`",
            f"- accepted_large_ratio_pct: `{summary['accepted_large_ratio_pct']}`",
            f"- generated_mutations: `{summary['generated_mutations']}`",
            f"- reproducible_mutations: `{summary['reproducible_mutations']}`",
            f"- selected_mutation_models: `{summary['selected_mutation_models']}`",
            f"- selected_mutation_models_total: `{summary['selected_mutation_models_total']}`",
            f"- max_mutation_models: `{summary['max_mutation_models']}`",
            f"- failure_types_count: `{summary['failure_types_count']}`",
            f"- mutations_per_failure_type: `{summary['mutations_per_failure_type']}`",
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
