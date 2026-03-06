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
MUTANT_ROOT="${GATEFORGE_MUTANT_ROOT:-$OUT_DIR/mutants}"
FAILURE_TYPES="${GATEFORGE_FAILURE_TYPES:-simulate_error,model_check_error,semantic_regression,numerical_instability,constraint_violation}"
CANONICAL_REGISTRY_PATH="${GATEFORGE_CANONICAL_REGISTRY_PATH:-artifacts/private_model_canonical_registry_v2/registry.json}"
CANONICAL_RUN_TAG="${GATEFORGE_CANONICAL_RUN_TAG:-$(date -u +%Y%m%dT%H%M%SZ)}"
VALIDATION_BACKEND="${GATEFORGE_MUTATION_VALIDATION_BACKEND:-auto}"
VALIDATION_TIMEOUT_SECONDS="${GATEFORGE_MUTATION_VALIDATION_TIMEOUT_SECONDS:-20}"
VALIDATION_MAX_BASELINES="${GATEFORGE_MUTATION_VALIDATION_MAX_BASELINES:-200}"
VALIDATION_MAX_MUTATIONS="${GATEFORGE_MUTATION_VALIDATION_MAX_MUTATIONS:-1200}"
VALIDATION_MIN_STAGE_MATCH_PCT="${GATEFORGE_MUTATION_VALIDATION_MIN_STAGE_MATCH_PCT:-25}"
VALIDATION_MIN_TYPE_MATCH_PCT="${GATEFORGE_MUTATION_VALIDATION_MIN_TYPE_MATCH_PCT:-15}"
MANIFEST_BASELINE_PATH="${GATEFORGE_MUTATION_MANIFEST_BASELINE_PATH:-$OUT_DIR/state/previous_mutation_manifest.json}"
SCALE_HISTORY_LEDGER_PATH="${GATEFORGE_SCALE_HISTORY_LEDGER_PATH:-$OUT_DIR/state/scale_history.jsonl}"
ACTION_BACKLOG_HISTORY_LEDGER_PATH="${GATEFORGE_ACTION_BACKLOG_HISTORY_LEDGER_PATH:-$OUT_DIR/state/action_backlog_history.jsonl}"
ACTION_BACKLOG_HISTORY_LAST_SUMMARY_PATH="${GATEFORGE_ACTION_BACKLOG_HISTORY_LAST_SUMMARY_PATH:-$OUT_DIR/state/action_backlog_history_last_summary.json}"
MUTATION_SELECTION_HISTORY_LEDGER_PATH="${GATEFORGE_MUTATION_SELECTION_HISTORY_LEDGER_PATH:-$OUT_DIR/state/mutation_selection_history.jsonl}"
MUTATION_SELECTION_HISTORY_LAST_SUMMARY_PATH="${GATEFORGE_MUTATION_SELECTION_HISTORY_LAST_SUMMARY_PATH:-$OUT_DIR/state/mutation_selection_history_last_summary.json}"
MUTATION_REPRO_DEPTH_HISTORY_LEDGER_PATH="${GATEFORGE_MUTATION_REPRO_DEPTH_HISTORY_LEDGER_PATH:-$OUT_DIR/state/mutation_repro_depth_history.jsonl}"
MUTATION_REPRO_DEPTH_HISTORY_LAST_SUMMARY_PATH="${GATEFORGE_MUTATION_REPRO_DEPTH_HISTORY_LAST_SUMMARY_PATH:-$OUT_DIR/state/mutation_repro_depth_history_last_summary.json}"
REAL_MODEL_SOURCE_DIVERSITY_HISTORY_LEDGER_PATH="${GATEFORGE_REAL_MODEL_SOURCE_DIVERSITY_HISTORY_LEDGER_PATH:-$OUT_DIR/state/real_model_source_diversity_history.jsonl}"
REAL_MODEL_SOURCE_DIVERSITY_HISTORY_LAST_SUMMARY_PATH="${GATEFORGE_REAL_MODEL_SOURCE_DIVERSITY_HISTORY_LAST_SUMMARY_PATH:-$OUT_DIR/state/real_model_source_diversity_history_last_summary.json}"
NET_GROWTH_AUTH_HISTORY_LEDGER_PATH="${GATEFORGE_NET_GROWTH_AUTH_HISTORY_LEDGER_PATH:-$OUT_DIR/state/net_growth_authenticity_history.jsonl}"
NET_GROWTH_AUTH_HISTORY_LAST_SUMMARY_PATH="${GATEFORGE_NET_GROWTH_AUTH_HISTORY_LAST_SUMMARY_PATH:-$OUT_DIR/state/net_growth_authenticity_history_last_summary.json}"
LARGE_MODEL_TRUTH_HISTORY_LEDGER_PATH="${GATEFORGE_LARGE_MODEL_TRUTH_HISTORY_LEDGER_PATH:-$OUT_DIR/state/large_model_executable_truth_history.jsonl}"
LARGE_MODEL_TRUTH_HISTORY_LAST_SUMMARY_PATH="${GATEFORGE_LARGE_MODEL_TRUTH_HISTORY_LAST_SUMMARY_PATH:-$OUT_DIR/state/large_model_executable_truth_last_summary.json}"
JOINT_MOAT_STRENGTH_HISTORY_LEDGER_PATH="${GATEFORGE_JOINT_MOAT_STRENGTH_HISTORY_LEDGER_PATH:-$OUT_DIR/state/joint_moat_strength_history.jsonl}"
JOINT_MOAT_STRENGTH_HISTORY_LAST_SUMMARY_PATH="${GATEFORGE_JOINT_MOAT_STRENGTH_HISTORY_LAST_SUMMARY_PATH:-$OUT_DIR/state/joint_moat_strength_last_summary.json}"
MUTATION_SIGNATURE_HISTORY_LEDGER_PATH="${GATEFORGE_MUTATION_SIGNATURE_HISTORY_LEDGER_PATH:-$OUT_DIR/state/mutation_signature_uniqueness_history.jsonl}"
MUTATION_SIGNATURE_HISTORY_LAST_SUMMARY_PATH="${GATEFORGE_MUTATION_SIGNATURE_HISTORY_LAST_SUMMARY_PATH:-$OUT_DIR/state/mutation_signature_uniqueness_last_summary.json}"
MUTATION_EXECUTION_AUTH_HISTORY_LEDGER_PATH="${GATEFORGE_MUTATION_EXECUTION_AUTH_HISTORY_LEDGER_PATH:-$OUT_DIR/state/mutation_execution_authenticity_history.jsonl}"
MUTATION_EXECUTION_AUTH_HISTORY_LAST_SUMMARY_PATH="${GATEFORGE_MUTATION_EXECUTION_AUTH_HISTORY_LAST_SUMMARY_PATH:-$OUT_DIR/state/mutation_execution_authenticity_last_summary.json}"
MUTATION_FAILURE_SIGNAL_HISTORY_LEDGER_PATH="${GATEFORGE_MUTATION_FAILURE_SIGNAL_HISTORY_LEDGER_PATH:-$OUT_DIR/state/mutation_failure_signal_authenticity_history.jsonl}"
MUTATION_FAILURE_SIGNAL_HISTORY_LAST_SUMMARY_PATH="${GATEFORGE_MUTATION_FAILURE_SIGNAL_HISTORY_LAST_SUMMARY_PATH:-$OUT_DIR/state/mutation_failure_signal_authenticity_last_summary.json}"
MUTATION_EFFECTIVE_SCALE_HISTORY_LEDGER_PATH="${GATEFORGE_MUTATION_EFFECTIVE_SCALE_HISTORY_LEDGER_PATH:-$OUT_DIR/state/mutation_effective_scale_history.jsonl}"
MUTATION_EFFECTIVE_SCALE_HISTORY_LAST_SUMMARY_PATH="${GATEFORGE_MUTATION_EFFECTIVE_SCALE_HISTORY_LAST_SUMMARY_PATH:-$OUT_DIR/state/mutation_effective_scale_last_summary.json}"
MUTATION_EFFECTIVE_DEPTH_HISTORY_LEDGER_PATH="${GATEFORGE_MUTATION_EFFECTIVE_DEPTH_HISTORY_LEDGER_PATH:-$OUT_DIR/state/mutation_effective_depth_history.jsonl}"
MUTATION_EFFECTIVE_DEPTH_HISTORY_LAST_SUMMARY_PATH="${GATEFORGE_MUTATION_EFFECTIVE_DEPTH_HISTORY_LAST_SUMMARY_PATH:-$OUT_DIR/state/mutation_effective_depth_last_summary.json}"
MUTATION_SOURCE_PROVENANCE_HISTORY_LEDGER_PATH="${GATEFORGE_MUTATION_SOURCE_PROVENANCE_HISTORY_LEDGER_PATH:-$OUT_DIR/state/mutation_source_provenance_history.jsonl}"
MUTATION_SOURCE_PROVENANCE_HISTORY_LAST_SUMMARY_PATH="${GATEFORGE_MUTATION_SOURCE_PROVENANCE_HISTORY_LAST_SUMMARY_PATH:-$OUT_DIR/state/mutation_source_provenance_last_summary.json}"
MUTATION_AUTHENTIC_SCALE_SCORE_HISTORY_LEDGER_PATH="${GATEFORGE_MUTATION_AUTHENTIC_SCALE_SCORE_HISTORY_LEDGER_PATH:-$OUT_DIR/state/mutation_authentic_scale_score_history.jsonl}"
MUTATION_AUTHENTIC_SCALE_SCORE_HISTORY_LAST_SUMMARY_PATH="${GATEFORGE_MUTATION_AUTHENTIC_SCALE_SCORE_HISTORY_LAST_SUMMARY_PATH:-$OUT_DIR/state/mutation_authentic_scale_score_last_summary.json}"
LARGE_MODEL_AUTHENTICITY_HISTORY_LEDGER_PATH="${GATEFORGE_LARGE_MODEL_AUTHENTICITY_HISTORY_LEDGER_PATH:-$OUT_DIR/state/large_model_authenticity_history.jsonl}"
LARGE_MODEL_AUTHENTICITY_HISTORY_LAST_SUMMARY_PATH="${GATEFORGE_LARGE_MODEL_AUTHENTICITY_HISTORY_LAST_SUMMARY_PATH:-$OUT_DIR/state/large_model_authenticity_last_summary.json}"
MUTATION_SOURCE_BUCKET_EFFECTIVE_SCALE_HISTORY_LEDGER_PATH="${GATEFORGE_MUTATION_SOURCE_BUCKET_EFFECTIVE_SCALE_HISTORY_LEDGER_PATH:-$OUT_DIR/state/mutation_source_bucket_effective_scale_history.jsonl}"
MUTATION_SOURCE_BUCKET_EFFECTIVE_SCALE_HISTORY_LAST_SUMMARY_PATH="${GATEFORGE_MUTATION_SOURCE_BUCKET_EFFECTIVE_SCALE_HISTORY_LAST_SUMMARY_PATH:-$OUT_DIR/state/mutation_source_bucket_effective_scale_last_summary.json}"
HARD_MOAT_MIN_DISCOVERED_MODELS="${GATEFORGE_HARD_MOAT_MIN_DISCOVERED_MODELS:-2}"
HARD_MOAT_MIN_ACCEPTED_MODELS="${GATEFORGE_HARD_MOAT_MIN_ACCEPTED_MODELS:-2}"
HARD_MOAT_MIN_ACCEPTED_LARGE_MODELS="${GATEFORGE_HARD_MOAT_MIN_ACCEPTED_LARGE_MODELS:-1}"
HARD_MOAT_MIN_ACCEPTED_LARGE_RATIO_PCT="${GATEFORGE_HARD_MOAT_MIN_ACCEPTED_LARGE_RATIO_PCT:-25}"
HARD_MOAT_MIN_GENERATED_MUTATIONS="${GATEFORGE_HARD_MOAT_MIN_GENERATED_MUTATIONS:-20}"
HARD_MOAT_MIN_REPRODUCIBLE_MUTATIONS="${GATEFORGE_HARD_MOAT_MIN_REPRODUCIBLE_MUTATIONS:-10}"
HARD_MOAT_MIN_CANONICAL_NET_GROWTH_MODELS="${GATEFORGE_HARD_MOAT_MIN_CANONICAL_NET_GROWTH_MODELS:-0}"
HARD_MOAT_MIN_VALIDATION_TYPE_MATCH_RATE_PCT="${GATEFORGE_HARD_MOAT_MIN_VALIDATION_TYPE_MATCH_RATE_PCT:-30}"
HARD_MOAT_MIN_FAILURE_TYPE_ENTROPY="${GATEFORGE_HARD_MOAT_MIN_FAILURE_TYPE_ENTROPY:-1.0}"
HARD_MOAT_MAX_DISTRIBUTION_DRIFT_TVD="${GATEFORGE_HARD_MOAT_MAX_DISTRIBUTION_DRIFT_TVD:-0.4}"
export TARGET_SCALES
export FAILURE_TYPES
export PROFILE
export DISCOVERY_MIN_MEDIUM_COMPLEXITY_SCORE
export DISCOVERY_MIN_LARGE_COMPLEXITY_SCORE
export MIN_ACCEPTED_LARGE_RATIO_PCT
export MAX_MUTATION_MODELS
export MUTANT_ROOT
export CANONICAL_REGISTRY_PATH
export CANONICAL_RUN_TAG
export VALIDATION_BACKEND
export VALIDATION_TIMEOUT_SECONDS
export VALIDATION_MAX_BASELINES
export VALIDATION_MAX_MUTATIONS
export VALIDATION_MIN_STAGE_MATCH_PCT
export VALIDATION_MIN_TYPE_MATCH_PCT
export MANIFEST_BASELINE_PATH
export SCALE_HISTORY_LEDGER_PATH
export ACTION_BACKLOG_HISTORY_LEDGER_PATH
export ACTION_BACKLOG_HISTORY_LAST_SUMMARY_PATH
export MUTATION_SELECTION_HISTORY_LEDGER_PATH
export MUTATION_SELECTION_HISTORY_LAST_SUMMARY_PATH
export MUTATION_REPRO_DEPTH_HISTORY_LEDGER_PATH
export MUTATION_REPRO_DEPTH_HISTORY_LAST_SUMMARY_PATH
export REAL_MODEL_SOURCE_DIVERSITY_HISTORY_LEDGER_PATH
export REAL_MODEL_SOURCE_DIVERSITY_HISTORY_LAST_SUMMARY_PATH
export NET_GROWTH_AUTH_HISTORY_LEDGER_PATH
export NET_GROWTH_AUTH_HISTORY_LAST_SUMMARY_PATH
export LARGE_MODEL_TRUTH_HISTORY_LEDGER_PATH
export LARGE_MODEL_TRUTH_HISTORY_LAST_SUMMARY_PATH
export JOINT_MOAT_STRENGTH_HISTORY_LEDGER_PATH
export JOINT_MOAT_STRENGTH_HISTORY_LAST_SUMMARY_PATH
export MUTATION_SIGNATURE_HISTORY_LEDGER_PATH
export MUTATION_SIGNATURE_HISTORY_LAST_SUMMARY_PATH
export MUTATION_EXECUTION_AUTH_HISTORY_LEDGER_PATH
export MUTATION_EXECUTION_AUTH_HISTORY_LAST_SUMMARY_PATH
export MUTATION_FAILURE_SIGNAL_HISTORY_LEDGER_PATH
export MUTATION_FAILURE_SIGNAL_HISTORY_LAST_SUMMARY_PATH
export MUTATION_EFFECTIVE_SCALE_HISTORY_LEDGER_PATH
export MUTATION_EFFECTIVE_SCALE_HISTORY_LAST_SUMMARY_PATH
export MUTATION_EFFECTIVE_DEPTH_HISTORY_LEDGER_PATH
export MUTATION_EFFECTIVE_DEPTH_HISTORY_LAST_SUMMARY_PATH
export MUTATION_SOURCE_PROVENANCE_HISTORY_LEDGER_PATH
export MUTATION_SOURCE_PROVENANCE_HISTORY_LAST_SUMMARY_PATH
export MUTATION_AUTHENTIC_SCALE_SCORE_HISTORY_LEDGER_PATH
export MUTATION_AUTHENTIC_SCALE_SCORE_HISTORY_LAST_SUMMARY_PATH
export LARGE_MODEL_AUTHENTICITY_HISTORY_LEDGER_PATH
export LARGE_MODEL_AUTHENTICITY_HISTORY_LAST_SUMMARY_PATH
export MUTATION_SOURCE_BUCKET_EFFECTIVE_SCALE_HISTORY_LEDGER_PATH
export MUTATION_SOURCE_BUCKET_EFFECTIVE_SCALE_HISTORY_LAST_SUMMARY_PATH
export HARD_MOAT_MIN_DISCOVERED_MODELS
export HARD_MOAT_MIN_ACCEPTED_MODELS
export HARD_MOAT_MIN_ACCEPTED_LARGE_MODELS
export HARD_MOAT_MIN_ACCEPTED_LARGE_RATIO_PCT
export HARD_MOAT_MIN_GENERATED_MUTATIONS
export HARD_MOAT_MIN_REPRODUCIBLE_MUTATIONS
export HARD_MOAT_MIN_CANONICAL_NET_GROWTH_MODELS
export HARD_MOAT_MIN_VALIDATION_TYPE_MATCH_RATE_PCT
export HARD_MOAT_MIN_FAILURE_TYPE_ENTROPY
export HARD_MOAT_MAX_DISTRIBUTION_DRIFT_TVD

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
    "mutant_root": os.environ.get("MUTANT_ROOT"),
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

python3 -m gateforge.dataset_real_model_executable_pool_v1 \
  --intake-registry-rows "$OUT_DIR/intake_registry_rows.json" \
  --intake-runner-accepted "$OUT_DIR/intake_runner_accepted.json" \
  --out-registry "$OUT_DIR/executable_registry_rows.json" \
  --out "$OUT_DIR/executable_pool_summary.json" \
  --report-out "$OUT_DIR/executable_pool_summary.md"

python3 -m gateforge.dataset_real_model_canonical_registry_v2 \
  --current-executable-registry "$OUT_DIR/executable_registry_rows.json" \
  --previous-canonical-registry "$CANONICAL_REGISTRY_PATH" \
  --run-tag "$CANONICAL_RUN_TAG" \
  --out-registry "$CANONICAL_REGISTRY_PATH" \
  --out "$OUT_DIR/canonical_registry_summary.json" \
  --report-out "$OUT_DIR/canonical_registry_summary.md"

python3 -m gateforge.dataset_real_model_net_growth_authenticity_gate_v1 \
  --canonical-registry-summary "$OUT_DIR/canonical_registry_summary.json" \
  --canonical-registry "$CANONICAL_REGISTRY_PATH" \
  --out "$OUT_DIR/real_model_net_growth_authenticity_summary.json" \
  --report-out "$OUT_DIR/real_model_net_growth_authenticity_summary.md"

if [ -f "$NET_GROWTH_AUTH_HISTORY_LAST_SUMMARY_PATH" ]; then
  cp "$NET_GROWTH_AUTH_HISTORY_LAST_SUMMARY_PATH" "$OUT_DIR/real_model_net_growth_authenticity_history_previous_summary.json"
else
  rm -f "$OUT_DIR/real_model_net_growth_authenticity_history_previous_summary.json"
fi

python3 -m gateforge.dataset_real_model_net_growth_authenticity_history_ledger_v1 \
  --net-growth-authenticity-summary "$OUT_DIR/real_model_net_growth_authenticity_summary.json" \
  --canonical-registry-summary "$OUT_DIR/canonical_registry_summary.json" \
  --intake-runner-summary "$OUT_DIR/intake_runner_summary.json" \
  --ledger "$NET_GROWTH_AUTH_HISTORY_LEDGER_PATH" \
  --out "$OUT_DIR/real_model_net_growth_authenticity_history_summary.json" \
  --report-out "$OUT_DIR/real_model_net_growth_authenticity_history_summary.md"

if [ -f "$OUT_DIR/real_model_net_growth_authenticity_history_previous_summary.json" ]; then
  python3 -m gateforge.dataset_real_model_net_growth_authenticity_history_trend_v1 \
    --previous "$OUT_DIR/real_model_net_growth_authenticity_history_previous_summary.json" \
    --current "$OUT_DIR/real_model_net_growth_authenticity_history_summary.json" \
    --out "$OUT_DIR/real_model_net_growth_authenticity_history_trend_summary.json" \
    --report-out "$OUT_DIR/real_model_net_growth_authenticity_history_trend_summary.md"
else
  cat > "$OUT_DIR/real_model_net_growth_authenticity_history_trend_summary.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "BOOTSTRAP->BOOTSTRAP",
    "delta_net_new_unique_models": 0,
    "delta_true_growth_ratio_pct": 0.0,
    "delta_suspected_duplicate_ratio_pct": 0.0,
    "alerts": []
  },
  "alerts": []
}
JSON
fi
mkdir -p "$(dirname "$NET_GROWTH_AUTH_HISTORY_LAST_SUMMARY_PATH")"
cp "$OUT_DIR/real_model_net_growth_authenticity_history_summary.json" "$NET_GROWTH_AUTH_HISTORY_LAST_SUMMARY_PATH"

python3 -m gateforge.dataset_modelica_mutation_recipe_library_v2 \
  --executable-pool-summary "$OUT_DIR/executable_pool_summary.json" \
  --target-scales "$TARGET_SCALES" \
  --recipes-out "$OUT_DIR/mutation_recipe_library_v2_recipes.json" \
  --out "$OUT_DIR/mutation_recipe_library_v2_summary.json" \
  --report-out "$OUT_DIR/mutation_recipe_library_v2_summary.md"

# Auto-scale mutation density based on accepted medium/large models and min-generated target.
python3 - <<'PY'
import json
import math
import os
from pathlib import Path

out = Path(os.environ["OUT_DIR"])
registry = json.loads((out / "executable_registry_rows.json").read_text(encoding="utf-8"))
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

python3 -m gateforge.dataset_mutation_model_selection_plan_v1 \
  --executable-registry "$OUT_DIR/executable_registry_rows.json" \
  --target-scales "$TARGET_SCALES" \
  --max-models "${MAX_MUTATION_MODELS}" \
  --min-large-ratio-pct "${MIN_ACCEPTED_LARGE_RATIO_PCT}" \
  --plan-out "$OUT_DIR/mutation_model_selection_plan.json" \
  --out "$OUT_DIR/mutation_model_selection_plan_summary.json" \
  --report-out "$OUT_DIR/mutation_model_selection_plan_summary.md"

python3 -m gateforge.dataset_mutation_model_materializer_v1 \
  --model-registry "$OUT_DIR/executable_registry_rows.json" \
  --selection-plan "$OUT_DIR/mutation_model_selection_plan.json" \
  --target-scales "$TARGET_SCALES" \
  --failure-types "$FAILURE_TYPES" \
  --recipe-library "$OUT_DIR/mutation_recipe_library_v2_recipes.json" \
  --mutations-per-recipe "${AUTO_MUTATIONS_PER_FAILURE_TYPE}" \
  --mutations-per-failure-type "${AUTO_MUTATIONS_PER_FAILURE_TYPE}" \
  --max-models "${MAX_MUTATION_MODELS}" \
  --mutant-root "${MUTANT_ROOT}" \
  --manifest-out "$OUT_DIR/mutation_manifest.json" \
  --out "$OUT_DIR/mutation_pack_summary.json" \
  --report-out "$OUT_DIR/mutation_pack_summary.md"

python3 -m gateforge.dataset_mutation_selection_balance_guard_v1 \
  --selection-plan-summary "$OUT_DIR/mutation_model_selection_plan_summary.json" \
  --mutation-pack-summary "$OUT_DIR/mutation_pack_summary.json" \
  --min-selected-models "${GATEFORGE_MIN_SELECTED_MODELS:-4}" \
  --min-large-ratio-pct "${MIN_ACCEPTED_LARGE_RATIO_PCT}" \
  --out "$OUT_DIR/mutation_selection_balance_guard_summary.json" \
  --report-out "$OUT_DIR/mutation_selection_balance_guard_summary.md"

if [ -f "$MUTATION_SELECTION_HISTORY_LAST_SUMMARY_PATH" ]; then
  cp "$MUTATION_SELECTION_HISTORY_LAST_SUMMARY_PATH" "$OUT_DIR/mutation_selection_history_previous_summary.json"
else
  rm -f "$OUT_DIR/mutation_selection_history_previous_summary.json"
fi

python3 -m gateforge.dataset_mutation_selection_history_ledger_v1 \
  --selection-plan-summary "$OUT_DIR/mutation_model_selection_plan_summary.json" \
  --selection-balance-guard-summary "$OUT_DIR/mutation_selection_balance_guard_summary.json" \
  --mutation-pack-summary "$OUT_DIR/mutation_pack_summary.json" \
  --ledger "$MUTATION_SELECTION_HISTORY_LEDGER_PATH" \
  --out "$OUT_DIR/mutation_selection_history_summary.json" \
  --report-out "$OUT_DIR/mutation_selection_history_summary.md"

if [ -f "$OUT_DIR/mutation_selection_history_previous_summary.json" ]; then
  python3 -m gateforge.dataset_mutation_selection_history_trend_v1 \
    --previous "$OUT_DIR/mutation_selection_history_previous_summary.json" \
    --current "$OUT_DIR/mutation_selection_history_summary.json" \
    --out "$OUT_DIR/mutation_selection_history_trend_summary.json" \
    --report-out "$OUT_DIR/mutation_selection_history_trend_summary.md"
else
  cat > "$OUT_DIR/mutation_selection_history_trend_summary.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "BOOTSTRAP->BOOTSTRAP",
    "delta_selected_large_ratio_pct": 0.0,
    "delta_selected_family_coverage": 0,
    "delta_selected_source_coverage": 0,
    "delta_max_family_share_pct": 0.0,
    "alerts": []
  },
  "alerts": []
}
JSON
fi
mkdir -p "$(dirname "$MUTATION_SELECTION_HISTORY_LAST_SUMMARY_PATH")"
cp "$OUT_DIR/mutation_selection_history_summary.json" "$MUTATION_SELECTION_HISTORY_LAST_SUMMARY_PATH"

python3 -m gateforge.dataset_mutation_validation_matrix_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --backend "$VALIDATION_BACKEND" \
  --timeout-seconds "$VALIDATION_TIMEOUT_SECONDS" \
  --max-baseline-models "$VALIDATION_MAX_BASELINES" \
  --max-validated-mutations "$VALIDATION_MAX_MUTATIONS" \
  --min-stage-match-rate-pct "$VALIDATION_MIN_STAGE_MATCH_PCT" \
  --min-type-match-rate-pct "$VALIDATION_MIN_TYPE_MATCH_PCT" \
  --records-out "$OUT_DIR/mutation_validation_records.json" \
  --out "$OUT_DIR/mutation_validation_summary.json" \
  --report-out "$OUT_DIR/mutation_validation_summary.md"

python3 -m gateforge.dataset_mutation_validation_matrix_v2 \
  --validation-records "$OUT_DIR/mutation_validation_records.json" \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --matrix-out "$OUT_DIR/mutation_validation_matrix_v2_matrix.json" \
  --out "$OUT_DIR/mutation_validation_matrix_v2_summary.json" \
  --report-out "$OUT_DIR/mutation_validation_matrix_v2_summary.md"

GUARD_ARGS=(
  --current-mutation-manifest "$OUT_DIR/mutation_manifest.json"
)
if [ -f "$MANIFEST_BASELINE_PATH" ]; then
  GUARD_ARGS+=(--previous-mutation-manifest "$MANIFEST_BASELINE_PATH")
fi

python3 -m gateforge.dataset_failure_distribution_stability_guard_v1 \
  "${GUARD_ARGS[@]}" \
  --out "$OUT_DIR/failure_distribution_stability_guard_summary.json" \
  --report-out "$OUT_DIR/failure_distribution_stability_guard_summary.md"

python3 -m gateforge.dataset_mutation_mismatch_triage_dataset_v1 \
  --validation-records "$OUT_DIR/mutation_validation_records.json" \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --triage-dataset-out "$OUT_DIR/mutation_mismatch_triage_dataset.json" \
  --out "$OUT_DIR/mutation_mismatch_triage_summary.json" \
  --report-out "$OUT_DIR/mutation_mismatch_triage_summary.md"

python3 -m gateforge.dataset_mutation_coverage_gap_backfill_v1 \
  --validation-matrix-v2-summary "$OUT_DIR/mutation_validation_matrix_v2_summary.json" \
  --failure-distribution-stability-guard-summary "$OUT_DIR/failure_distribution_stability_guard_summary.json" \
  --tasks-out "$OUT_DIR/mutation_coverage_backfill_tasks.json" \
  --out "$OUT_DIR/mutation_coverage_backfill_summary.json" \
  --report-out "$OUT_DIR/mutation_coverage_backfill_summary.md"

python3 -m gateforge.dataset_mutation_failure_type_balance_guard_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --mutation-validation-records "$OUT_DIR/mutation_validation_records.json" \
  --out "$OUT_DIR/mutation_failure_type_balance_guard_summary.json" \
  --report-out "$OUT_DIR/mutation_failure_type_balance_guard_summary.md"

python3 -m gateforge.dataset_ingest_source_channel_planner_v1 \
  --asset-discovery-summary "$OUT_DIR/asset_discovery_summary.json" \
  --intake-runner-summary "$OUT_DIR/intake_runner_summary.json" \
  --canonical-registry-summary "$OUT_DIR/canonical_registry_summary.json" \
  --coverage-backfill-summary "$OUT_DIR/mutation_coverage_backfill_summary.json" \
  --profile-config "$OUT_DIR/profile_config.json" \
  --plan-out "$OUT_DIR/ingest_source_channel_plan.json" \
  --out "$OUT_DIR/ingest_source_channel_planner_summary.json" \
  --report-out "$OUT_DIR/ingest_source_channel_planner_summary.md"

python3 -m gateforge.dataset_hard_moat_target_profile_v1 \
  --profile-config "$OUT_DIR/profile_config.json" \
  --ingest-source-channel-planner-summary "$OUT_DIR/ingest_source_channel_planner_summary.json" \
  --asset-discovery-summary "$OUT_DIR/asset_discovery_summary.json" \
  --intake-runner-summary "$OUT_DIR/intake_runner_summary.json" \
  --mutation-pack-summary "$OUT_DIR/mutation_pack_summary.json" \
  --canonical-registry-summary "$OUT_DIR/canonical_registry_summary.json" \
  --coverage-backfill-summary "$OUT_DIR/mutation_coverage_backfill_summary.json" \
  --target-profile-out "$OUT_DIR/hard_moat_target_profile.json" \
  --out "$OUT_DIR/hard_moat_target_profile_summary.json" \
  --report-out "$OUT_DIR/hard_moat_target_profile_summary.md"

python3 - <<'PY'
import json
import os
from pathlib import Path

out = Path(os.environ["OUT_DIR"])
summary = json.loads((out / "hard_moat_target_profile_summary.json").read_text(encoding="utf-8"))
thresholds = summary.get("thresholds") if isinstance(summary.get("thresholds"), dict) else {}

mapping = {
    "HARD_MOAT_MIN_DISCOVERED_MODELS": int(thresholds.get("min_discovered_models", os.environ.get("HARD_MOAT_MIN_DISCOVERED_MODELS", "2"))),
    "HARD_MOAT_MIN_ACCEPTED_MODELS": int(thresholds.get("min_accepted_models", os.environ.get("HARD_MOAT_MIN_ACCEPTED_MODELS", "2"))),
    "HARD_MOAT_MIN_ACCEPTED_LARGE_MODELS": int(thresholds.get("min_accepted_large_models", os.environ.get("HARD_MOAT_MIN_ACCEPTED_LARGE_MODELS", "1"))),
    "HARD_MOAT_MIN_ACCEPTED_LARGE_RATIO_PCT": float(thresholds.get("min_accepted_large_ratio_pct", os.environ.get("HARD_MOAT_MIN_ACCEPTED_LARGE_RATIO_PCT", "25"))),
    "HARD_MOAT_MIN_GENERATED_MUTATIONS": int(thresholds.get("min_generated_mutations", os.environ.get("HARD_MOAT_MIN_GENERATED_MUTATIONS", "20"))),
    "HARD_MOAT_MIN_REPRODUCIBLE_MUTATIONS": int(thresholds.get("min_reproducible_mutations", os.environ.get("HARD_MOAT_MIN_REPRODUCIBLE_MUTATIONS", "10"))),
    "HARD_MOAT_MIN_CANONICAL_NET_GROWTH_MODELS": int(thresholds.get("min_canonical_net_growth_models", os.environ.get("HARD_MOAT_MIN_CANONICAL_NET_GROWTH_MODELS", "0"))),
    "HARD_MOAT_MIN_VALIDATION_TYPE_MATCH_RATE_PCT": float(thresholds.get("min_validation_type_match_rate_pct", os.environ.get("HARD_MOAT_MIN_VALIDATION_TYPE_MATCH_RATE_PCT", "30"))),
    "HARD_MOAT_MIN_FAILURE_TYPE_ENTROPY": float(thresholds.get("min_failure_type_entropy", os.environ.get("HARD_MOAT_MIN_FAILURE_TYPE_ENTROPY", "1.0"))),
    "HARD_MOAT_MAX_DISTRIBUTION_DRIFT_TVD": float(thresholds.get("max_distribution_drift_tvd", os.environ.get("HARD_MOAT_MAX_DISTRIBUTION_DRIFT_TVD", "0.4"))),
}

lines = [f"{key}={value}" for key, value in mapping.items()]
(out / "hard_moat_target_profile.env").write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
source "$OUT_DIR/hard_moat_target_profile.env"

mkdir -p "$(dirname "$MANIFEST_BASELINE_PATH")"
cp "$OUT_DIR/mutation_manifest.json" "$MANIFEST_BASELINE_PATH"

python3 -m gateforge.dataset_mutation_real_runner_v1 \
  --validated-mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --timeout-seconds "${GATEFORGE_MUTATION_TIMEOUT_SECONDS:-15}" \
  --max-retries "0" \
  --raw-observations-out "$OUT_DIR/mutation_raw_observations.json" \
  --out "$OUT_DIR/mutation_real_runner_summary.json" \
  --report-out "$OUT_DIR/mutation_real_runner_summary.md"

python3 -m gateforge.dataset_mutation_execution_authenticity_guard_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --mutation-raw-observations "$OUT_DIR/mutation_raw_observations.json" \
  --out "$OUT_DIR/mutation_execution_authenticity_summary.json" \
  --report-out "$OUT_DIR/mutation_execution_authenticity_summary.md"

if [ -f "$MUTATION_EXECUTION_AUTH_HISTORY_LAST_SUMMARY_PATH" ]; then
  cp "$MUTATION_EXECUTION_AUTH_HISTORY_LAST_SUMMARY_PATH" "$OUT_DIR/mutation_execution_authenticity_history_previous_summary.json"
else
  rm -f "$OUT_DIR/mutation_execution_authenticity_history_previous_summary.json"
fi

python3 -m gateforge.dataset_mutation_execution_authenticity_history_ledger_v1 \
  --mutation-execution-authenticity-summary "$OUT_DIR/mutation_execution_authenticity_summary.json" \
  --ledger "$MUTATION_EXECUTION_AUTH_HISTORY_LEDGER_PATH" \
  --out "$OUT_DIR/mutation_execution_authenticity_history_summary.json" \
  --report-out "$OUT_DIR/mutation_execution_authenticity_history_summary.md"

if [ -f "$OUT_DIR/mutation_execution_authenticity_history_previous_summary.json" ]; then
  python3 -m gateforge.dataset_mutation_execution_authenticity_history_trend_v1 \
    --previous "$OUT_DIR/mutation_execution_authenticity_history_previous_summary.json" \
    --current "$OUT_DIR/mutation_execution_authenticity_history_summary.json" \
    --out "$OUT_DIR/mutation_execution_authenticity_history_trend_summary.json" \
    --report-out "$OUT_DIR/mutation_execution_authenticity_history_trend_summary.md"
else
  cat > "$OUT_DIR/mutation_execution_authenticity_history_trend_summary.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "BOOTSTRAP->BOOTSTRAP",
    "delta_solver_command_ratio_pct": 0.0,
    "delta_probe_only_command_ratio_pct": 0.0,
    "alerts": []
  },
  "alerts": []
}
JSON
fi
mkdir -p "$(dirname "$MUTATION_EXECUTION_AUTH_HISTORY_LAST_SUMMARY_PATH")"
cp "$OUT_DIR/mutation_execution_authenticity_history_summary.json" "$MUTATION_EXECUTION_AUTH_HISTORY_LAST_SUMMARY_PATH"

python3 -m gateforge.dataset_mutation_failure_signal_authenticity_guard_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --mutation-raw-observations "$OUT_DIR/mutation_raw_observations.json" \
  --out "$OUT_DIR/mutation_failure_signal_authenticity_summary.json" \
  --report-out "$OUT_DIR/mutation_failure_signal_authenticity_summary.md"

if [ -f "$MUTATION_FAILURE_SIGNAL_HISTORY_LAST_SUMMARY_PATH" ]; then
  cp "$MUTATION_FAILURE_SIGNAL_HISTORY_LAST_SUMMARY_PATH" "$OUT_DIR/mutation_failure_signal_authenticity_history_previous_summary.json"
else
  rm -f "$OUT_DIR/mutation_failure_signal_authenticity_history_previous_summary.json"
fi

python3 -m gateforge.dataset_mutation_failure_signal_authenticity_history_ledger_v1 \
  --mutation-failure-signal-authenticity-summary "$OUT_DIR/mutation_failure_signal_authenticity_summary.json" \
  --ledger "$MUTATION_FAILURE_SIGNAL_HISTORY_LEDGER_PATH" \
  --out "$OUT_DIR/mutation_failure_signal_authenticity_history_summary.json" \
  --report-out "$OUT_DIR/mutation_failure_signal_authenticity_history_summary.md"

if [ -f "$OUT_DIR/mutation_failure_signal_authenticity_history_previous_summary.json" ]; then
  python3 -m gateforge.dataset_mutation_failure_signal_authenticity_history_trend_v1 \
    --previous "$OUT_DIR/mutation_failure_signal_authenticity_history_previous_summary.json" \
    --current "$OUT_DIR/mutation_failure_signal_authenticity_history_summary.json" \
    --out "$OUT_DIR/mutation_failure_signal_authenticity_history_trend_summary.json" \
    --report-out "$OUT_DIR/mutation_failure_signal_authenticity_history_trend_summary.md"
else
  cat > "$OUT_DIR/mutation_failure_signal_authenticity_history_trend_summary.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "BOOTSTRAP->BOOTSTRAP",
    "delta_failure_signal_ratio_pct": 0.0,
    "delta_expected_failure_type_signal_coverage_pct": 0.0,
    "alerts": []
  },
  "alerts": []
}
JSON
fi
mkdir -p "$(dirname "$MUTATION_FAILURE_SIGNAL_HISTORY_LAST_SUMMARY_PATH")"
cp "$OUT_DIR/mutation_failure_signal_authenticity_history_summary.json" "$MUTATION_FAILURE_SIGNAL_HISTORY_LAST_SUMMARY_PATH"

python3 -m gateforge.dataset_mutation_repro_depth_guard_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --mutation-raw-observations "$OUT_DIR/mutation_raw_observations.json" \
  --selection-plan "$OUT_DIR/mutation_model_selection_plan.json" \
  --min-reproducible-mutations-per-model "${GATEFORGE_MIN_REPRO_DEPTH_PER_MODEL:-6}" \
  --min-large-model-reproducible-mutations-per-model "${GATEFORGE_MIN_LARGE_REPRO_DEPTH_PER_MODEL:-8}" \
  --out "$OUT_DIR/mutation_repro_depth_guard_summary.json" \
  --report-out "$OUT_DIR/mutation_repro_depth_guard_summary.md"

if [ -f "$MUTATION_REPRO_DEPTH_HISTORY_LAST_SUMMARY_PATH" ]; then
  cp "$MUTATION_REPRO_DEPTH_HISTORY_LAST_SUMMARY_PATH" "$OUT_DIR/mutation_repro_depth_history_previous_summary.json"
else
  rm -f "$OUT_DIR/mutation_repro_depth_history_previous_summary.json"
fi

python3 -m gateforge.dataset_mutation_repro_depth_history_ledger_v1 \
  --mutation-repro-depth-guard-summary "$OUT_DIR/mutation_repro_depth_guard_summary.json" \
  --mutation-pack-summary "$OUT_DIR/mutation_pack_summary.json" \
  --mutation-real-runner-summary "$OUT_DIR/mutation_real_runner_summary.json" \
  --ledger "$MUTATION_REPRO_DEPTH_HISTORY_LEDGER_PATH" \
  --out "$OUT_DIR/mutation_repro_depth_history_summary.json" \
  --report-out "$OUT_DIR/mutation_repro_depth_history_summary.md"

if [ -f "$OUT_DIR/mutation_repro_depth_history_previous_summary.json" ]; then
  python3 -m gateforge.dataset_mutation_repro_depth_history_trend_v1 \
    --previous "$OUT_DIR/mutation_repro_depth_history_previous_summary.json" \
    --current "$OUT_DIR/mutation_repro_depth_history_summary.json" \
    --out "$OUT_DIR/mutation_repro_depth_history_trend_summary.json" \
    --report-out "$OUT_DIR/mutation_repro_depth_history_trend_summary.md"
else
  cat > "$OUT_DIR/mutation_repro_depth_history_trend_summary.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "BOOTSTRAP->BOOTSTRAP",
    "delta_depth_ratio_pct": 0.0,
    "delta_p10_depth": 0.0,
    "delta_concentration_pct": 0.0,
    "alerts": []
  },
  "alerts": []
}
JSON
fi
mkdir -p "$(dirname "$MUTATION_REPRO_DEPTH_HISTORY_LAST_SUMMARY_PATH")"
cp "$OUT_DIR/mutation_repro_depth_history_summary.json" "$MUTATION_REPRO_DEPTH_HISTORY_LAST_SUMMARY_PATH"

python3 -m gateforge.dataset_mutation_effective_depth_guard_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --mutation-raw-observations "$OUT_DIR/mutation_raw_observations.json" \
  --selection-plan "$OUT_DIR/mutation_model_selection_plan.json" \
  --out "$OUT_DIR/mutation_effective_depth_summary.json" \
  --report-out "$OUT_DIR/mutation_effective_depth_summary.md"

if [ -f "$MUTATION_EFFECTIVE_DEPTH_HISTORY_LAST_SUMMARY_PATH" ]; then
  cp "$MUTATION_EFFECTIVE_DEPTH_HISTORY_LAST_SUMMARY_PATH" "$OUT_DIR/mutation_effective_depth_history_previous_summary.json"
else
  rm -f "$OUT_DIR/mutation_effective_depth_history_previous_summary.json"
fi

python3 -m gateforge.dataset_mutation_effective_depth_history_ledger_v1 \
  --mutation-effective-depth-summary "$OUT_DIR/mutation_effective_depth_summary.json" \
  --ledger "$MUTATION_EFFECTIVE_DEPTH_HISTORY_LEDGER_PATH" \
  --out "$OUT_DIR/mutation_effective_depth_history_summary.json" \
  --report-out "$OUT_DIR/mutation_effective_depth_history_summary.md"

if [ -f "$OUT_DIR/mutation_effective_depth_history_previous_summary.json" ]; then
  python3 -m gateforge.dataset_mutation_effective_depth_history_trend_v1 \
    --previous "$OUT_DIR/mutation_effective_depth_history_previous_summary.json" \
    --current "$OUT_DIR/mutation_effective_depth_history_summary.json" \
    --out "$OUT_DIR/mutation_effective_depth_history_trend_summary.json" \
    --report-out "$OUT_DIR/mutation_effective_depth_history_trend_summary.md"
else
  cat > "$OUT_DIR/mutation_effective_depth_history_trend_summary.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "BOOTSTRAP->BOOTSTRAP",
    "delta_total_effective_mutations": 0,
    "delta_p10_effective_mutations_per_model": 0.0,
    "alerts": []
  },
  "alerts": []
}
JSON
fi
mkdir -p "$(dirname "$MUTATION_EFFECTIVE_DEPTH_HISTORY_LAST_SUMMARY_PATH")"
cp "$OUT_DIR/mutation_effective_depth_history_summary.json" "$MUTATION_EFFECTIVE_DEPTH_HISTORY_LAST_SUMMARY_PATH"

python3 -m gateforge.dataset_mutation_source_provenance_guard_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --executable-registry "$OUT_DIR/executable_registry_rows.json" \
  --allowed-model-roots "$ROOTS_RAW" \
  --out "$OUT_DIR/mutation_source_provenance_summary.json" \
  --report-out "$OUT_DIR/mutation_source_provenance_summary.md"

if [ -f "$MUTATION_SOURCE_PROVENANCE_HISTORY_LAST_SUMMARY_PATH" ]; then
  cp "$MUTATION_SOURCE_PROVENANCE_HISTORY_LAST_SUMMARY_PATH" "$OUT_DIR/mutation_source_provenance_history_previous_summary.json"
else
  rm -f "$OUT_DIR/mutation_source_provenance_history_previous_summary.json"
fi

python3 -m gateforge.dataset_mutation_source_provenance_history_ledger_v1 \
  --mutation-source-provenance-summary "$OUT_DIR/mutation_source_provenance_summary.json" \
  --ledger "$MUTATION_SOURCE_PROVENANCE_HISTORY_LEDGER_PATH" \
  --out "$OUT_DIR/mutation_source_provenance_history_summary.json" \
  --report-out "$OUT_DIR/mutation_source_provenance_history_summary.md"

if [ -f "$OUT_DIR/mutation_source_provenance_history_previous_summary.json" ]; then
  python3 -m gateforge.dataset_mutation_source_provenance_history_trend_v1 \
    --previous "$OUT_DIR/mutation_source_provenance_history_previous_summary.json" \
    --current "$OUT_DIR/mutation_source_provenance_history_summary.json" \
    --out "$OUT_DIR/mutation_source_provenance_history_trend_summary.json" \
    --report-out "$OUT_DIR/mutation_source_provenance_history_trend_summary.md"
else
  cat > "$OUT_DIR/mutation_source_provenance_history_trend_summary.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "BOOTSTRAP->BOOTSTRAP",
    "delta_existing_source_path_ratio_pct": 0.0,
    "delta_allowed_root_ratio_pct": 0.0,
    "alerts": []
  },
  "alerts": []
}
JSON
fi
mkdir -p "$(dirname "$MUTATION_SOURCE_PROVENANCE_HISTORY_LAST_SUMMARY_PATH")"
cp "$OUT_DIR/mutation_source_provenance_history_summary.json" "$MUTATION_SOURCE_PROVENANCE_HISTORY_LAST_SUMMARY_PATH"

python3 -m gateforge.dataset_mutation_authentic_scale_score_v1 \
  --mutation-execution-authenticity-summary "$OUT_DIR/mutation_execution_authenticity_summary.json" \
  --mutation-failure-signal-authenticity-summary "$OUT_DIR/mutation_failure_signal_authenticity_summary.json" \
  --mutation-effective-depth-summary "$OUT_DIR/mutation_effective_depth_summary.json" \
  --mutation-source-provenance-summary "$OUT_DIR/mutation_source_provenance_summary.json" \
  --out "$OUT_DIR/mutation_authentic_scale_score_summary.json" \
  --report-out "$OUT_DIR/mutation_authentic_scale_score_summary.md"

if [ -f "$MUTATION_AUTHENTIC_SCALE_SCORE_HISTORY_LAST_SUMMARY_PATH" ]; then
  cp "$MUTATION_AUTHENTIC_SCALE_SCORE_HISTORY_LAST_SUMMARY_PATH" "$OUT_DIR/mutation_authentic_scale_score_history_previous_summary.json"
else
  rm -f "$OUT_DIR/mutation_authentic_scale_score_history_previous_summary.json"
fi

python3 -m gateforge.dataset_mutation_authentic_scale_score_history_ledger_v1 \
  --mutation-authentic-scale-score-summary "$OUT_DIR/mutation_authentic_scale_score_summary.json" \
  --ledger "$MUTATION_AUTHENTIC_SCALE_SCORE_HISTORY_LEDGER_PATH" \
  --out "$OUT_DIR/mutation_authentic_scale_score_history_summary.json" \
  --report-out "$OUT_DIR/mutation_authentic_scale_score_history_summary.md"

if [ -f "$OUT_DIR/mutation_authentic_scale_score_history_previous_summary.json" ]; then
  python3 -m gateforge.dataset_mutation_authentic_scale_score_history_trend_v1 \
    --previous "$OUT_DIR/mutation_authentic_scale_score_history_previous_summary.json" \
    --current "$OUT_DIR/mutation_authentic_scale_score_history_summary.json" \
    --out "$OUT_DIR/mutation_authentic_scale_score_history_trend_summary.json" \
    --report-out "$OUT_DIR/mutation_authentic_scale_score_history_trend_summary.md"
else
  cat > "$OUT_DIR/mutation_authentic_scale_score_history_trend_summary.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "BOOTSTRAP->BOOTSTRAP",
    "delta_authentic_scale_score": 0.0,
    "alerts": []
  },
  "alerts": []
}
JSON
fi
mkdir -p "$(dirname "$MUTATION_AUTHENTIC_SCALE_SCORE_HISTORY_LAST_SUMMARY_PATH")"
cp "$OUT_DIR/mutation_authentic_scale_score_history_summary.json" "$MUTATION_AUTHENTIC_SCALE_SCORE_HISTORY_LAST_SUMMARY_PATH"

python3 -m gateforge.dataset_mutation_source_bucket_effective_scale_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --mutation-raw-observations "$OUT_DIR/mutation_raw_observations.json" \
  --out "$OUT_DIR/mutation_source_bucket_effective_scale_summary.json" \
  --report-out "$OUT_DIR/mutation_source_bucket_effective_scale_summary.md"

if [ -f "$MUTATION_SOURCE_BUCKET_EFFECTIVE_SCALE_HISTORY_LAST_SUMMARY_PATH" ]; then
  cp "$MUTATION_SOURCE_BUCKET_EFFECTIVE_SCALE_HISTORY_LAST_SUMMARY_PATH" "$OUT_DIR/mutation_source_bucket_effective_scale_history_previous_summary.json"
else
  rm -f "$OUT_DIR/mutation_source_bucket_effective_scale_history_previous_summary.json"
fi

python3 -m gateforge.dataset_mutation_source_bucket_effective_scale_history_ledger_v1 \
  --mutation-source-bucket-effective-scale-summary "$OUT_DIR/mutation_source_bucket_effective_scale_summary.json" \
  --ledger "$MUTATION_SOURCE_BUCKET_EFFECTIVE_SCALE_HISTORY_LEDGER_PATH" \
  --out "$OUT_DIR/mutation_source_bucket_effective_scale_history_summary.json" \
  --report-out "$OUT_DIR/mutation_source_bucket_effective_scale_history_summary.md"

if [ -f "$OUT_DIR/mutation_source_bucket_effective_scale_history_previous_summary.json" ]; then
  python3 -m gateforge.dataset_mutation_source_bucket_effective_scale_history_trend_v1 \
    --previous "$OUT_DIR/mutation_source_bucket_effective_scale_history_previous_summary.json" \
    --current "$OUT_DIR/mutation_source_bucket_effective_scale_history_summary.json" \
    --out "$OUT_DIR/mutation_source_bucket_effective_scale_history_trend_summary.json" \
    --report-out "$OUT_DIR/mutation_source_bucket_effective_scale_history_trend_summary.md"
else
  cat > "$OUT_DIR/mutation_source_bucket_effective_scale_history_trend_summary.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "BOOTSTRAP->BOOTSTRAP",
    "delta_source_bucket_count": 0,
    "delta_effective_mutations": 0,
    "delta_max_bucket_share_pct": 0.0,
    "alerts": []
  },
  "alerts": []
}
JSON
fi
mkdir -p "$(dirname "$MUTATION_SOURCE_BUCKET_EFFECTIVE_SCALE_HISTORY_LAST_SUMMARY_PATH")"
cp "$OUT_DIR/mutation_source_bucket_effective_scale_history_summary.json" "$MUTATION_SOURCE_BUCKET_EFFECTIVE_SCALE_HISTORY_LAST_SUMMARY_PATH"

python3 -m gateforge.dataset_large_model_executable_truth_gate_v1 \
  --executable-registry "$OUT_DIR/executable_registry_rows.json" \
  --mutation-validation-records "$OUT_DIR/mutation_validation_records.json" \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --mutation-raw-observations "$OUT_DIR/mutation_raw_observations.json" \
  --out "$OUT_DIR/large_model_executable_truth_summary.json" \
  --report-out "$OUT_DIR/large_model_executable_truth_summary.md"

if [ -f "$LARGE_MODEL_TRUTH_HISTORY_LAST_SUMMARY_PATH" ]; then
  cp "$LARGE_MODEL_TRUTH_HISTORY_LAST_SUMMARY_PATH" "$OUT_DIR/large_model_executable_truth_history_previous_summary.json"
else
  rm -f "$OUT_DIR/large_model_executable_truth_history_previous_summary.json"
fi

python3 -m gateforge.dataset_large_model_executable_truth_history_ledger_v1 \
  --large-model-executable-truth-summary "$OUT_DIR/large_model_executable_truth_summary.json" \
  --intake-runner-summary "$OUT_DIR/intake_runner_summary.json" \
  --ledger "$LARGE_MODEL_TRUTH_HISTORY_LEDGER_PATH" \
  --out "$OUT_DIR/large_model_executable_truth_history_summary.json" \
  --report-out "$OUT_DIR/large_model_executable_truth_history_summary.md"

if [ -f "$OUT_DIR/large_model_executable_truth_history_previous_summary.json" ]; then
  python3 -m gateforge.dataset_large_model_executable_truth_history_trend_v1 \
    --previous "$OUT_DIR/large_model_executable_truth_history_previous_summary.json" \
    --current "$OUT_DIR/large_model_executable_truth_history_summary.json" \
    --out "$OUT_DIR/large_model_executable_truth_history_trend_summary.json" \
    --report-out "$OUT_DIR/large_model_executable_truth_history_trend_summary.md"
else
  cat > "$OUT_DIR/large_model_executable_truth_history_trend_summary.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "BOOTSTRAP->BOOTSTRAP",
    "delta_large_executable_real_count": 0,
    "delta_large_executable_real_rate_pct": 0.0,
    "delta_large_model_check_pass_rate_pct": 0.0,
    "alerts": []
  },
  "alerts": []
}
JSON
fi
mkdir -p "$(dirname "$LARGE_MODEL_TRUTH_HISTORY_LAST_SUMMARY_PATH")"
cp "$OUT_DIR/large_model_executable_truth_history_summary.json" "$LARGE_MODEL_TRUTH_HISTORY_LAST_SUMMARY_PATH"

python3 -m gateforge.dataset_large_model_authenticity_gate_v1 \
  --large-model-executable-truth-summary "$OUT_DIR/large_model_executable_truth_summary.json" \
  --mutation-effective-depth-summary "$OUT_DIR/mutation_effective_depth_summary.json" \
  --mutation-source-provenance-summary "$OUT_DIR/mutation_source_provenance_summary.json" \
  --mutation-authentic-scale-score-summary "$OUT_DIR/mutation_authentic_scale_score_summary.json" \
  --out "$OUT_DIR/large_model_authenticity_summary.json" \
  --report-out "$OUT_DIR/large_model_authenticity_summary.md" \
  || true

if [ -f "$LARGE_MODEL_AUTHENTICITY_HISTORY_LAST_SUMMARY_PATH" ]; then
  cp "$LARGE_MODEL_AUTHENTICITY_HISTORY_LAST_SUMMARY_PATH" "$OUT_DIR/large_model_authenticity_history_previous_summary.json"
else
  rm -f "$OUT_DIR/large_model_authenticity_history_previous_summary.json"
fi

python3 -m gateforge.dataset_large_model_authenticity_history_ledger_v1 \
  --large-model-authenticity-summary "$OUT_DIR/large_model_authenticity_summary.json" \
  --ledger "$LARGE_MODEL_AUTHENTICITY_HISTORY_LEDGER_PATH" \
  --out "$OUT_DIR/large_model_authenticity_history_summary.json" \
  --report-out "$OUT_DIR/large_model_authenticity_history_summary.md"

if [ -f "$OUT_DIR/large_model_authenticity_history_previous_summary.json" ]; then
  python3 -m gateforge.dataset_large_model_authenticity_history_trend_v1 \
    --previous "$OUT_DIR/large_model_authenticity_history_previous_summary.json" \
    --current "$OUT_DIR/large_model_authenticity_history_summary.json" \
    --out "$OUT_DIR/large_model_authenticity_history_trend_summary.json" \
    --report-out "$OUT_DIR/large_model_authenticity_history_trend_summary.md"
else
  cat > "$OUT_DIR/large_model_authenticity_history_trend_summary.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "BOOTSTRAP->BOOTSTRAP",
    "delta_large_model_authenticity_score": 0.0,
    "alerts": []
  },
  "alerts": []
}
JSON
fi
mkdir -p "$(dirname "$LARGE_MODEL_AUTHENTICITY_HISTORY_LAST_SUMMARY_PATH")"
cp "$OUT_DIR/large_model_authenticity_history_summary.json" "$LARGE_MODEL_AUTHENTICITY_HISTORY_LAST_SUMMARY_PATH"

python3 -m gateforge.dataset_moat_weekly_target_gate_v1 \
  --intake-runner-summary "$OUT_DIR/intake_runner_summary.json" \
  --mutation-real-runner-summary "$OUT_DIR/mutation_real_runner_summary.json" \
  --large-model-authenticity-summary "$OUT_DIR/large_model_authenticity_summary.json" \
  --out "$OUT_DIR/moat_weekly_target_gate_summary.json" \
  --report-out "$OUT_DIR/moat_weekly_target_gate_summary.md"

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

python3 -m gateforge.dataset_hard_moat_gates_v1 \
  --asset-discovery-summary "$OUT_DIR/asset_discovery_summary.json" \
  --intake-runner-summary "$OUT_DIR/intake_runner_summary.json" \
  --canonical-registry-summary "$OUT_DIR/canonical_registry_summary.json" \
  --mutation-pack-summary "$OUT_DIR/mutation_pack_summary.json" \
  --mutation-real-runner-summary "$OUT_DIR/mutation_real_runner_summary.json" \
  --mutation-validation-matrix-v2-summary "$OUT_DIR/mutation_validation_matrix_v2_summary.json" \
  --failure-distribution-stability-guard-summary "$OUT_DIR/failure_distribution_stability_guard_summary.json" \
  --mutation-effective-scale-summary "$OUT_DIR/mutation_effective_scale_summary.json" \
  --mutation-effective-depth-summary "$OUT_DIR/mutation_effective_depth_summary.json" \
  --mutation-source-provenance-summary "$OUT_DIR/mutation_source_provenance_summary.json" \
  --mutation-authentic-scale-score-summary "$OUT_DIR/mutation_authentic_scale_score_summary.json" \
  --large-model-authenticity-gate-summary "$OUT_DIR/large_model_authenticity_summary.json" \
  --mutation-source-bucket-effective-scale-summary "$OUT_DIR/mutation_source_bucket_effective_scale_summary.json" \
  --mutation-authentic-scale-score-trend-summary "$OUT_DIR/mutation_authentic_scale_score_history_trend_summary.json" \
  --large-model-authenticity-trend-summary "$OUT_DIR/large_model_authenticity_history_trend_summary.json" \
  --mutation-source-bucket-effective-scale-trend-summary "$OUT_DIR/mutation_source_bucket_effective_scale_history_trend_summary.json" \
  --min-discovered-models "$HARD_MOAT_MIN_DISCOVERED_MODELS" \
  --min-accepted-models "$HARD_MOAT_MIN_ACCEPTED_MODELS" \
  --min-accepted-large-models "$HARD_MOAT_MIN_ACCEPTED_LARGE_MODELS" \
  --min-accepted-large-ratio-pct "$HARD_MOAT_MIN_ACCEPTED_LARGE_RATIO_PCT" \
  --min-generated-mutations "$HARD_MOAT_MIN_GENERATED_MUTATIONS" \
  --min-reproducible-mutations "$HARD_MOAT_MIN_REPRODUCIBLE_MUTATIONS" \
  --min-canonical-net-growth-models "$HARD_MOAT_MIN_CANONICAL_NET_GROWTH_MODELS" \
  --min-validation-type-match-rate-pct "$HARD_MOAT_MIN_VALIDATION_TYPE_MATCH_RATE_PCT" \
  --min-failure-type-entropy "$HARD_MOAT_MIN_FAILURE_TYPE_ENTROPY" \
  --max-distribution-drift-tvd "$HARD_MOAT_MAX_DISTRIBUTION_DRIFT_TVD" \
  --out "$OUT_DIR/hard_moat_gates_summary.json" \
  --report-out "$OUT_DIR/hard_moat_gates_summary.md" \
  || true

python3 -m gateforge.dataset_real_model_pool_audit_v1 \
  --executable-registry "$OUT_DIR/executable_registry_rows.json" \
  --intake-runner-accepted "$OUT_DIR/intake_runner_accepted.json" \
  --out "$OUT_DIR/real_model_pool_audit_summary.json" \
  --report-out "$OUT_DIR/real_model_pool_audit_summary.md"

python3 -m gateforge.dataset_real_model_family_coverage_board_v1 \
  --executable-registry "$OUT_DIR/executable_registry_rows.json" \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --out "$OUT_DIR/real_model_family_coverage_board_summary.json" \
  --report-out "$OUT_DIR/real_model_family_coverage_board_summary.md"

python3 -m gateforge.dataset_real_model_source_diversity_guard_v1 \
  --executable-registry "$OUT_DIR/executable_registry_rows.json" \
  --out "$OUT_DIR/real_model_source_diversity_guard_summary.json" \
  --report-out "$OUT_DIR/real_model_source_diversity_guard_summary.md"

if [ -f "$REAL_MODEL_SOURCE_DIVERSITY_HISTORY_LAST_SUMMARY_PATH" ]; then
  cp "$REAL_MODEL_SOURCE_DIVERSITY_HISTORY_LAST_SUMMARY_PATH" "$OUT_DIR/real_model_source_diversity_history_previous_summary.json"
else
  rm -f "$OUT_DIR/real_model_source_diversity_history_previous_summary.json"
fi

python3 -m gateforge.dataset_real_model_source_diversity_history_ledger_v1 \
  --source-diversity-guard-summary "$OUT_DIR/real_model_source_diversity_guard_summary.json" \
  --asset-discovery-summary "$OUT_DIR/asset_discovery_summary.json" \
  --intake-runner-summary "$OUT_DIR/intake_runner_summary.json" \
  --ledger "$REAL_MODEL_SOURCE_DIVERSITY_HISTORY_LEDGER_PATH" \
  --out "$OUT_DIR/real_model_source_diversity_history_summary.json" \
  --report-out "$OUT_DIR/real_model_source_diversity_history_summary.md"

if [ -f "$OUT_DIR/real_model_source_diversity_history_previous_summary.json" ]; then
  python3 -m gateforge.dataset_real_model_source_diversity_history_trend_v1 \
    --previous "$OUT_DIR/real_model_source_diversity_history_previous_summary.json" \
    --current "$OUT_DIR/real_model_source_diversity_history_summary.json" \
    --out "$OUT_DIR/real_model_source_diversity_history_trend_summary.json" \
    --report-out "$OUT_DIR/real_model_source_diversity_history_trend_summary.md"
else
  cat > "$OUT_DIR/real_model_source_diversity_history_trend_summary.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "BOOTSTRAP->BOOTSTRAP",
    "delta_unique_source_buckets": 0,
    "delta_unique_large_source_buckets": 0,
    "delta_max_source_bucket_share_pct": 0.0,
    "alerts": []
  },
  "alerts": []
}
JSON
fi
mkdir -p "$(dirname "$REAL_MODEL_SOURCE_DIVERSITY_HISTORY_LAST_SUMMARY_PATH")"
cp "$OUT_DIR/real_model_source_diversity_history_summary.json" "$REAL_MODEL_SOURCE_DIVERSITY_HISTORY_LAST_SUMMARY_PATH"

python3 -m gateforge.dataset_joint_moat_strength_gate_v1 \
  --real-model-family-coverage-summary "$OUT_DIR/real_model_family_coverage_board_summary.json" \
  --real-model-source-diversity-summary "$OUT_DIR/real_model_source_diversity_guard_summary.json" \
  --mutation-repro-depth-summary "$OUT_DIR/mutation_repro_depth_guard_summary.json" \
  --large-model-executable-truth-summary "$OUT_DIR/large_model_executable_truth_summary.json" \
  --real-model-net-growth-authenticity-summary "$OUT_DIR/real_model_net_growth_authenticity_summary.json" \
  --hard-moat-gates-summary "$OUT_DIR/hard_moat_gates_summary.json" \
  --mutation-execution-authenticity-summary "$OUT_DIR/mutation_execution_authenticity_summary.json" \
  --mutation-failure-signal-authenticity-summary "$OUT_DIR/mutation_failure_signal_authenticity_summary.json" \
  --mutation-effective-depth-summary "$OUT_DIR/mutation_effective_depth_summary.json" \
  --mutation-source-provenance-summary "$OUT_DIR/mutation_source_provenance_summary.json" \
  --mutation-authentic-scale-score-summary "$OUT_DIR/mutation_authentic_scale_score_summary.json" \
  --large-model-authenticity-gate-summary "$OUT_DIR/large_model_authenticity_summary.json" \
  --mutation-source-bucket-effective-scale-summary "$OUT_DIR/mutation_source_bucket_effective_scale_summary.json" \
  --mutation-authentic-scale-score-trend-summary "$OUT_DIR/mutation_authentic_scale_score_history_trend_summary.json" \
  --large-model-authenticity-trend-summary "$OUT_DIR/large_model_authenticity_history_trend_summary.json" \
  --mutation-source-bucket-effective-scale-trend-summary "$OUT_DIR/mutation_source_bucket_effective_scale_history_trend_summary.json" \
  --out "$OUT_DIR/joint_moat_strength_summary.json" \
  --report-out "$OUT_DIR/joint_moat_strength_summary.md" \
  || true

if [ -f "$JOINT_MOAT_STRENGTH_HISTORY_LAST_SUMMARY_PATH" ]; then
  cp "$JOINT_MOAT_STRENGTH_HISTORY_LAST_SUMMARY_PATH" "$OUT_DIR/joint_moat_strength_history_previous_summary.json"
else
  rm -f "$OUT_DIR/joint_moat_strength_history_previous_summary.json"
fi

python3 -m gateforge.dataset_joint_moat_strength_history_ledger_v1 \
  --joint-moat-strength-summary "$OUT_DIR/joint_moat_strength_summary.json" \
  --ledger "$JOINT_MOAT_STRENGTH_HISTORY_LEDGER_PATH" \
  --out "$OUT_DIR/joint_moat_strength_history_summary.json" \
  --report-out "$OUT_DIR/joint_moat_strength_history_summary.md"

if [ -f "$OUT_DIR/joint_moat_strength_history_previous_summary.json" ]; then
  python3 -m gateforge.dataset_joint_moat_strength_history_trend_v1 \
    --previous "$OUT_DIR/joint_moat_strength_history_previous_summary.json" \
    --current "$OUT_DIR/joint_moat_strength_history_summary.json" \
    --out "$OUT_DIR/joint_moat_strength_history_trend_summary.json" \
    --report-out "$OUT_DIR/joint_moat_strength_history_trend_summary.md"
else
  cat > "$OUT_DIR/joint_moat_strength_history_trend_summary.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "BOOTSTRAP->BOOTSTRAP",
    "delta_moat_strength_score": 0.0,
    "alerts": []
  },
  "alerts": []
}
JSON
fi
mkdir -p "$(dirname "$JOINT_MOAT_STRENGTH_HISTORY_LAST_SUMMARY_PATH")"
cp "$OUT_DIR/joint_moat_strength_history_summary.json" "$JOINT_MOAT_STRENGTH_HISTORY_LAST_SUMMARY_PATH"

python3 -m gateforge.dataset_mutation_signature_uniqueness_guard_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --out "$OUT_DIR/mutation_signature_uniqueness_summary.json" \
  --report-out "$OUT_DIR/mutation_signature_uniqueness_summary.md"

if [ -f "$MUTATION_SIGNATURE_HISTORY_LAST_SUMMARY_PATH" ]; then
  cp "$MUTATION_SIGNATURE_HISTORY_LAST_SUMMARY_PATH" "$OUT_DIR/mutation_signature_uniqueness_history_previous_summary.json"
else
  rm -f "$OUT_DIR/mutation_signature_uniqueness_history_previous_summary.json"
fi

python3 -m gateforge.dataset_mutation_signature_uniqueness_history_ledger_v1 \
  --mutation-signature-uniqueness-summary "$OUT_DIR/mutation_signature_uniqueness_summary.json" \
  --ledger "$MUTATION_SIGNATURE_HISTORY_LEDGER_PATH" \
  --out "$OUT_DIR/mutation_signature_uniqueness_history_summary.json" \
  --report-out "$OUT_DIR/mutation_signature_uniqueness_history_summary.md"

if [ -f "$OUT_DIR/mutation_signature_uniqueness_history_previous_summary.json" ]; then
  python3 -m gateforge.dataset_mutation_signature_uniqueness_history_trend_v1 \
    --previous "$OUT_DIR/mutation_signature_uniqueness_history_previous_summary.json" \
    --current "$OUT_DIR/mutation_signature_uniqueness_history_summary.json" \
    --out "$OUT_DIR/mutation_signature_uniqueness_history_trend_summary.json" \
    --report-out "$OUT_DIR/mutation_signature_uniqueness_history_trend_summary.md"
else
  cat > "$OUT_DIR/mutation_signature_uniqueness_history_trend_summary.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "BOOTSTRAP->BOOTSTRAP",
    "delta_unique_signature_ratio_pct": 0.0,
    "alerts": []
  },
  "alerts": []
}
JSON
fi
mkdir -p "$(dirname "$MUTATION_SIGNATURE_HISTORY_LAST_SUMMARY_PATH")"
cp "$OUT_DIR/mutation_signature_uniqueness_history_summary.json" "$MUTATION_SIGNATURE_HISTORY_LAST_SUMMARY_PATH"

python3 -m gateforge.dataset_mutation_effective_scale_guard_v1 \
  --mutation-pack-summary "$OUT_DIR/mutation_pack_summary.json" \
  --mutation-real-runner-summary "$OUT_DIR/mutation_real_runner_summary.json" \
  --mutation-signature-uniqueness-summary "$OUT_DIR/mutation_signature_uniqueness_summary.json" \
  --mutation-execution-authenticity-summary "$OUT_DIR/mutation_execution_authenticity_summary.json" \
  --mutation-failure-signal-authenticity-summary "$OUT_DIR/mutation_failure_signal_authenticity_summary.json" \
  --out "$OUT_DIR/mutation_effective_scale_summary.json" \
  --report-out "$OUT_DIR/mutation_effective_scale_summary.md"

if [ -f "$MUTATION_EFFECTIVE_SCALE_HISTORY_LAST_SUMMARY_PATH" ]; then
  cp "$MUTATION_EFFECTIVE_SCALE_HISTORY_LAST_SUMMARY_PATH" "$OUT_DIR/mutation_effective_scale_history_previous_summary.json"
else
  rm -f "$OUT_DIR/mutation_effective_scale_history_previous_summary.json"
fi

python3 -m gateforge.dataset_mutation_effective_scale_history_ledger_v1 \
  --mutation-effective-scale-summary "$OUT_DIR/mutation_effective_scale_summary.json" \
  --ledger "$MUTATION_EFFECTIVE_SCALE_HISTORY_LEDGER_PATH" \
  --out "$OUT_DIR/mutation_effective_scale_history_summary.json" \
  --report-out "$OUT_DIR/mutation_effective_scale_history_summary.md"

if [ -f "$OUT_DIR/mutation_effective_scale_history_previous_summary.json" ]; then
  python3 -m gateforge.dataset_mutation_effective_scale_history_trend_v1 \
    --previous "$OUT_DIR/mutation_effective_scale_history_previous_summary.json" \
    --current "$OUT_DIR/mutation_effective_scale_history_summary.json" \
    --out "$OUT_DIR/mutation_effective_scale_history_trend_summary.json" \
    --report-out "$OUT_DIR/mutation_effective_scale_history_trend_summary.md"
else
  cat > "$OUT_DIR/mutation_effective_scale_history_trend_summary.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "BOOTSTRAP->BOOTSTRAP",
    "delta_effective_reproducible_mutations": 0,
    "delta_authenticity_multiplier": 0.0,
    "alerts": []
  },
  "alerts": []
}
JSON
fi
mkdir -p "$(dirname "$MUTATION_EFFECTIVE_SCALE_HISTORY_LAST_SUMMARY_PATH")"
cp "$OUT_DIR/mutation_effective_scale_history_summary.json" "$MUTATION_EFFECTIVE_SCALE_HISTORY_LAST_SUMMARY_PATH"

python3 -m gateforge.dataset_mutation_artifact_inventory_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --mutation-raw-observations "$OUT_DIR/mutation_raw_observations.json" \
  --out "$OUT_DIR/mutation_artifact_inventory_summary.json" \
  --report-out "$OUT_DIR/mutation_artifact_inventory_summary.md"

python3 -m gateforge.dataset_asset_locator_manifest_v1 \
  --executable-registry "$OUT_DIR/executable_registry_rows.json" \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --out "$OUT_DIR/asset_locator_manifest_summary.json" \
  --report-out "$OUT_DIR/asset_locator_manifest_summary.md"

python3 -m gateforge.dataset_reproducible_mutation_sample_pack_v1 \
  --mutation-manifest "$OUT_DIR/mutation_manifest.json" \
  --mutation-raw-observations "$OUT_DIR/mutation_raw_observations.json" \
  --sample-size "${GATEFORGE_REPRO_SAMPLE_SIZE:-40}" \
  --sample-seed "${GATEFORGE_REPRO_SAMPLE_SEED:-gateforge-sample-v1}" \
  --pack-out "$OUT_DIR/reproducible_mutation_sample_pack.json" \
  --out "$OUT_DIR/reproducible_mutation_sample_pack_summary.json" \
  --report-out "$OUT_DIR/reproducible_mutation_sample_pack_summary.md"

python3 -m gateforge.dataset_scale_evidence_stamp_v1 \
  --real-model-pool-audit-summary "$OUT_DIR/real_model_pool_audit_summary.json" \
  --mutation-artifact-inventory-summary "$OUT_DIR/mutation_artifact_inventory_summary.json" \
  --scale-gate-summary "$OUT_DIR/scale_gate_summary.json" \
  --out "$OUT_DIR/scale_evidence_stamp_summary.json" \
  --report-out "$OUT_DIR/scale_evidence_stamp_summary.md"

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
executable = _load("executable_pool_summary.json")
canonical = _load("canonical_registry_summary.json")
net_growth_auth = _load("real_model_net_growth_authenticity_summary.json")
net_growth_auth_history = _load("real_model_net_growth_authenticity_history_summary.json")
net_growth_auth_history_trend = _load("real_model_net_growth_authenticity_history_trend_summary.json")
recipe = _load("mutation_recipe_library_v2_summary.json")
selection_plan = _load("mutation_model_selection_plan_summary.json")
pack = _load("mutation_pack_summary.json")
selection_guard = _load("mutation_selection_balance_guard_summary.json")
selection_history = _load("mutation_selection_history_summary.json")
selection_history_trend = _load("mutation_selection_history_trend_summary.json")
repro_depth_guard = _load("mutation_repro_depth_guard_summary.json")
repro_depth_history = _load("mutation_repro_depth_history_summary.json")
repro_depth_history_trend = _load("mutation_repro_depth_history_trend_summary.json")
validation = _load("mutation_validation_summary.json")
validation_v2 = _load("mutation_validation_matrix_v2_summary.json")
stability_guard = _load("failure_distribution_stability_guard_summary.json")
mismatch_triage = _load("mutation_mismatch_triage_summary.json")
coverage_backfill = _load("mutation_coverage_backfill_summary.json")
failure_balance = _load("mutation_failure_type_balance_guard_summary.json")
ingest_planner = _load("ingest_source_channel_planner_summary.json")
hard_moat_target = _load("hard_moat_target_profile_summary.json")
realrun = _load("mutation_real_runner_summary.json")
mutation_exec_auth = _load("mutation_execution_authenticity_summary.json")
mutation_exec_auth_history = _load("mutation_execution_authenticity_history_summary.json")
mutation_exec_auth_history_trend = _load("mutation_execution_authenticity_history_trend_summary.json")
mutation_failure_signal_auth = _load("mutation_failure_signal_authenticity_summary.json")
mutation_failure_signal_auth_history = _load("mutation_failure_signal_authenticity_history_summary.json")
mutation_failure_signal_auth_history_trend = _load("mutation_failure_signal_authenticity_history_trend_summary.json")
large_model_truth = _load("large_model_executable_truth_summary.json")
large_model_truth_history = _load("large_model_executable_truth_history_summary.json")
large_model_truth_history_trend = _load("large_model_executable_truth_history_trend_summary.json")
gate = _load("scale_gate_summary.json")
hard_moat = _load("hard_moat_gates_summary.json")
pool_audit = _load("real_model_pool_audit_summary.json")
family_board = _load("real_model_family_coverage_board_summary.json")
source_diversity_guard = _load("real_model_source_diversity_guard_summary.json")
source_diversity_history = _load("real_model_source_diversity_history_summary.json")
source_diversity_history_trend = _load("real_model_source_diversity_history_trend_summary.json")
joint_moat_strength = _load("joint_moat_strength_summary.json")
joint_moat_strength_history = _load("joint_moat_strength_history_summary.json")
joint_moat_strength_history_trend = _load("joint_moat_strength_history_trend_summary.json")
mutation_signature_uniqueness = _load("mutation_signature_uniqueness_summary.json")
mutation_signature_uniqueness_history = _load("mutation_signature_uniqueness_history_summary.json")
mutation_signature_uniqueness_history_trend = _load("mutation_signature_uniqueness_history_trend_summary.json")
mutation_effective_scale = _load("mutation_effective_scale_summary.json")
mutation_effective_scale_history = _load("mutation_effective_scale_history_summary.json")
mutation_effective_scale_history_trend = _load("mutation_effective_scale_history_trend_summary.json")
mutation_effective_depth = _load("mutation_effective_depth_summary.json")
mutation_effective_depth_history = _load("mutation_effective_depth_history_summary.json")
mutation_effective_depth_history_trend = _load("mutation_effective_depth_history_trend_summary.json")
mutation_source_provenance = _load("mutation_source_provenance_summary.json")
mutation_source_provenance_history = _load("mutation_source_provenance_history_summary.json")
mutation_source_provenance_history_trend = _load("mutation_source_provenance_history_trend_summary.json")
mutation_authentic_scale_score = _load("mutation_authentic_scale_score_summary.json")
mutation_authentic_scale_score_history = _load("mutation_authentic_scale_score_history_summary.json")
mutation_authentic_scale_score_history_trend = _load("mutation_authentic_scale_score_history_trend_summary.json")
mutation_source_bucket_effective_scale = _load("mutation_source_bucket_effective_scale_summary.json")
mutation_source_bucket_effective_scale_history = _load("mutation_source_bucket_effective_scale_history_summary.json")
mutation_source_bucket_effective_scale_history_trend = _load("mutation_source_bucket_effective_scale_history_trend_summary.json")
large_model_authenticity = _load("large_model_authenticity_summary.json")
large_model_authenticity_history = _load("large_model_authenticity_history_summary.json")
large_model_authenticity_history_trend = _load("large_model_authenticity_history_trend_summary.json")
moat_weekly_target_gate = _load("moat_weekly_target_gate_summary.json")
mutation_inventory = _load("mutation_artifact_inventory_summary.json")
asset_locator = _load("asset_locator_manifest_summary.json")
repro_sample_pack = _load("reproducible_mutation_sample_pack_summary.json")
evidence_stamp = _load("scale_evidence_stamp_summary.json")
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
    "executable_pool_present": "PASS" if int(executable.get("executable_unique_models", 0)) >= 0 else "FAIL",
    "canonical_registry_present": "PASS" if int(canonical.get("canonical_total_models", 0)) >= 0 else "FAIL",
    "net_growth_authenticity_exists": "PASS" if str(net_growth_auth.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "net_growth_authenticity_history_exists": "PASS" if str(net_growth_auth_history.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "net_growth_authenticity_history_trend_exists": "PASS" if str(net_growth_auth_history_trend.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "recipe_library_present": "PASS" if int(recipe.get("total_recipes", 0)) >= 0 else "FAIL",
    "selection_plan_exists": "PASS" if str(selection_plan.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "selection_history_exists": "PASS" if str(selection_history.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "selection_history_trend_exists": "PASS" if str(selection_history_trend.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "repro_depth_guard_exists": "PASS" if str(repro_depth_guard.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "repro_depth_history_exists": "PASS" if str(repro_depth_history.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "repro_depth_history_trend_exists": "PASS" if str(repro_depth_history_trend.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "large_model_truth_exists": "PASS" if str(large_model_truth.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "large_model_truth_history_exists": "PASS" if str(large_model_truth_history.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "large_model_truth_history_trend_exists": "PASS" if str(large_model_truth_history_trend.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_execution_authenticity_exists": "PASS" if str(mutation_exec_auth.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_execution_authenticity_history_exists": "PASS" if str(mutation_exec_auth_history.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_execution_authenticity_history_trend_exists": "PASS" if str(mutation_exec_auth_history_trend.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_failure_signal_authenticity_exists": "PASS" if str(mutation_failure_signal_auth.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_failure_signal_authenticity_history_exists": "PASS" if str(mutation_failure_signal_auth_history.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_failure_signal_authenticity_history_trend_exists": "PASS" if str(mutation_failure_signal_auth_history_trend.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "validation_exists": "PASS" if str(validation.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "validation_v2_exists": "PASS" if str(validation_v2.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "selection_balance_guard_exists": "PASS" if str(selection_guard.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "stability_guard_exists": "PASS" if str(stability_guard.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mismatch_triage_exists": "PASS" if str(mismatch_triage.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "coverage_backfill_exists": "PASS" if str(coverage_backfill.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "failure_type_balance_exists": "PASS" if str(failure_balance.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "ingest_source_channel_planner_exists": "PASS" if str(ingest_planner.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "hard_moat_target_profile_exists": "PASS" if str(hard_moat_target.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "real_model_pool_audit_exists": "PASS" if str(pool_audit.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "real_model_family_coverage_exists": "PASS" if str(family_board.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "real_model_source_diversity_guard_exists": "PASS" if str(source_diversity_guard.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "real_model_source_diversity_history_exists": "PASS" if str(source_diversity_history.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "real_model_source_diversity_history_trend_exists": "PASS" if str(source_diversity_history_trend.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "joint_moat_strength_exists": "PASS" if str(joint_moat_strength.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "joint_moat_strength_history_exists": "PASS" if str(joint_moat_strength_history.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "joint_moat_strength_history_trend_exists": "PASS" if str(joint_moat_strength_history_trend.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_signature_uniqueness_exists": "PASS" if str(mutation_signature_uniqueness.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_signature_uniqueness_history_exists": "PASS" if str(mutation_signature_uniqueness_history.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_signature_uniqueness_history_trend_exists": "PASS" if str(mutation_signature_uniqueness_history_trend.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_effective_scale_exists": "PASS" if str(mutation_effective_scale.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_effective_scale_history_exists": "PASS" if str(mutation_effective_scale_history.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_effective_scale_history_trend_exists": "PASS" if str(mutation_effective_scale_history_trend.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_effective_depth_exists": "PASS" if str(mutation_effective_depth.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_effective_depth_history_exists": "PASS" if str(mutation_effective_depth_history.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_effective_depth_history_trend_exists": "PASS" if str(mutation_effective_depth_history_trend.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_source_provenance_exists": "PASS" if str(mutation_source_provenance.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_source_provenance_history_exists": "PASS" if str(mutation_source_provenance_history.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_source_provenance_history_trend_exists": "PASS" if str(mutation_source_provenance_history_trend.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_authentic_scale_score_exists": "PASS" if str(mutation_authentic_scale_score.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_authentic_scale_score_history_exists": "PASS" if str(mutation_authentic_scale_score_history.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_authentic_scale_score_history_trend_exists": "PASS" if str(mutation_authentic_scale_score_history_trend.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_source_bucket_effective_scale_exists": "PASS" if str(mutation_source_bucket_effective_scale.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_source_bucket_effective_scale_history_exists": "PASS" if str(mutation_source_bucket_effective_scale_history.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_source_bucket_effective_scale_history_trend_exists": "PASS" if str(mutation_source_bucket_effective_scale_history_trend.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "large_model_authenticity_exists": "PASS" if str(large_model_authenticity.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "large_model_authenticity_history_exists": "PASS" if str(large_model_authenticity_history.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "large_model_authenticity_history_trend_exists": "PASS" if str(large_model_authenticity_history_trend.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "moat_weekly_target_gate_exists": "PASS" if str(moat_weekly_target_gate.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "mutation_artifact_inventory_exists": "PASS" if str(mutation_inventory.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "asset_locator_manifest_exists": "PASS" if str(asset_locator.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "reproducible_sample_pack_exists": "PASS" if str(repro_sample_pack.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "scale_evidence_stamp_exists": "PASS" if str(evidence_stamp.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "gate_status_present": "PASS" if str(gate.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
    "hard_moat_gates_status_present": "PASS" if str(hard_moat.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
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
    "raw_models": executable.get("raw_models"),
    "executable_unique_models": executable.get("executable_unique_models"),
    "executable_large_models": executable.get("executable_large_models"),
    "canonical_total_models": canonical.get("canonical_total_models"),
    "canonical_new_models": canonical.get("canonical_new_models"),
    "canonical_net_growth_models": canonical.get("canonical_net_growth_models"),
    "canonical_new_large_models": canonical.get("canonical_new_large_models"),
    "real_model_net_growth_authenticity_status": net_growth_auth.get("status"),
    "real_model_net_growth_authenticity_net_new_unique_models": net_growth_auth.get("net_new_unique_models"),
    "real_model_net_growth_authenticity_true_growth_ratio_pct": net_growth_auth.get("true_growth_ratio_pct"),
    "real_model_net_growth_authenticity_suspected_duplicate_ratio_pct": net_growth_auth.get("suspected_duplicate_ratio_pct"),
    "real_model_net_growth_authenticity_history_status": net_growth_auth_history.get("status"),
    "real_model_net_growth_authenticity_history_total_records": net_growth_auth_history.get("total_records"),
    "real_model_net_growth_authenticity_history_latest_net_new_unique_models": net_growth_auth_history.get("latest_net_new_unique_models"),
    "real_model_net_growth_authenticity_history_latest_true_growth_ratio_pct": net_growth_auth_history.get("latest_true_growth_ratio_pct"),
    "real_model_net_growth_authenticity_history_trend_status": net_growth_auth_history_trend.get("status"),
    "real_model_net_growth_authenticity_history_trend_delta_net_new_unique_models": (net_growth_auth_history_trend.get("trend") or {}).get("delta_net_new_unique_models"),
    "real_model_net_growth_authenticity_history_trend_delta_true_growth_ratio_pct": (net_growth_auth_history_trend.get("trend") or {}).get("delta_true_growth_ratio_pct"),
    "mutation_recipe_library_v2_status": recipe.get("status"),
    "mutation_recipe_total_recipes": recipe.get("total_recipes"),
    "mutation_recipe_operator_family_count": recipe.get("operator_family_count"),
    "mutation_selection_plan_status": selection_plan.get("status"),
    "mutation_selection_plan_selected_models": selection_plan.get("selected_models"),
    "mutation_selection_plan_selected_large_ratio_pct": selection_plan.get("selected_large_ratio_pct"),
    "mutation_selection_plan_selected_families": selection_plan.get("selected_families"),
    "mutation_selection_plan_selected_source_buckets": selection_plan.get("selected_source_buckets"),
    "mutation_selection_balance_guard_status": selection_guard.get("status"),
    "mutation_selection_balance_guard_max_family_share_pct": selection_guard.get("max_family_share_pct"),
    "mutation_selection_history_status": selection_history.get("status"),
    "mutation_selection_history_total_records": selection_history.get("total_records"),
    "mutation_selection_history_latest_selected_large_ratio_pct": selection_history.get("latest_selected_large_ratio_pct"),
    "mutation_selection_history_latest_max_family_share_pct": selection_history.get("latest_max_family_share_pct"),
    "mutation_selection_history_trend_status": selection_history_trend.get("status"),
    "mutation_selection_history_trend_delta_selected_large_ratio_pct": (selection_history_trend.get("trend") or {}).get("delta_selected_large_ratio_pct"),
    "mutation_selection_history_trend_delta_selected_family_coverage": (selection_history_trend.get("trend") or {}).get("delta_selected_family_coverage"),
    "mutation_selection_history_trend_delta_max_family_share_pct": (selection_history_trend.get("trend") or {}).get("delta_max_family_share_pct"),
    "mutation_repro_depth_guard_status": repro_depth_guard.get("status"),
    "mutation_repro_depth_guard_tracked_models": repro_depth_guard.get("tracked_models"),
    "mutation_repro_depth_guard_models_meeting_depth_ratio_pct": repro_depth_guard.get("models_meeting_depth_ratio_pct"),
    "mutation_repro_depth_guard_p10_reproducible_mutations_per_model": repro_depth_guard.get("p10_reproducible_mutations_per_model"),
    "mutation_repro_depth_guard_max_model_share_pct": repro_depth_guard.get("max_model_share_pct"),
    "mutation_repro_depth_history_status": repro_depth_history.get("status"),
    "mutation_repro_depth_history_total_records": repro_depth_history.get("total_records"),
    "mutation_repro_depth_history_latest_depth_ratio_pct": repro_depth_history.get("latest_models_meeting_depth_ratio_pct"),
    "mutation_repro_depth_history_latest_p10_depth": repro_depth_history.get("latest_p10_reproducible_mutations_per_model"),
    "mutation_repro_depth_history_latest_concentration_pct": repro_depth_history.get("latest_max_model_share_pct"),
    "mutation_repro_depth_history_trend_status": repro_depth_history_trend.get("status"),
    "mutation_repro_depth_history_trend_delta_depth_ratio_pct": (repro_depth_history_trend.get("trend") or {}).get("delta_depth_ratio_pct"),
    "mutation_repro_depth_history_trend_delta_p10_depth": (repro_depth_history_trend.get("trend") or {}).get("delta_p10_depth"),
    "mutation_repro_depth_history_trend_delta_concentration_pct": (repro_depth_history_trend.get("trend") or {}).get("delta_concentration_pct"),
    "generated_mutations": pack.get("total_mutations"),
    "materialized_mutations": pack.get("materialized_mutations"),
    "failed_materializations": pack.get("failed_materializations"),
    "mutation_validation_status": validation.get("status"),
    "validation_backend_used": validation.get("validation_backend_used"),
    "baseline_check_pass_rate_pct": validation.get("baseline_check_pass_rate_pct"),
    "validation_stage_match_rate_pct": validation.get("stage_match_rate_pct"),
    "validation_type_match_rate_pct": validation.get("type_match_rate_pct"),
    "validation_v2_status": validation_v2.get("status"),
    "validation_v2_medium_type_match_rate_pct": ((validation_v2.get("by_scale") or {}).get("medium") or {}).get("type_match_rate_pct"),
    "validation_v2_large_type_match_rate_pct": ((validation_v2.get("by_scale") or {}).get("large") or {}).get("type_match_rate_pct"),
    "validation_v2_overall_type_match_rate_pct": (validation_v2.get("overall") or {}).get("type_match_rate_pct"),
    "failure_distribution_guard_status": stability_guard.get("status"),
    "failure_distribution_guard_entropy": stability_guard.get("failure_type_entropy"),
    "failure_distribution_guard_drift_tvd": stability_guard.get("distribution_drift_tvd"),
    "mismatch_triage_status": mismatch_triage.get("status"),
    "mismatch_triage_count": mismatch_triage.get("mismatch_count"),
    "coverage_backfill_status": coverage_backfill.get("status"),
    "coverage_backfill_total_tasks": coverage_backfill.get("total_tasks"),
    "coverage_backfill_p0_tasks": coverage_backfill.get("p0_tasks"),
    "failure_type_balance_status": failure_balance.get("status"),
    "failure_type_balance_expected_count": failure_balance.get("expected_failure_type_count"),
    "failure_type_balance_expected_entropy": failure_balance.get("expected_entropy"),
    "ingest_source_channel_planner_status": ingest_planner.get("status"),
    "ingest_source_channel_planner_p0_channels": ingest_planner.get("p0_channels"),
    "ingest_source_channel_planner_planned_weekly_new_models": ingest_planner.get("planned_weekly_new_models"),
    "hard_moat_target_profile_status": hard_moat_target.get("status"),
    "hard_moat_target_profile_strictness_level": hard_moat_target.get("strictness_level"),
    "hard_moat_target_profile_weekly_model_target": hard_moat_target.get("weekly_model_target"),
    "hard_moat_target_profile_weekly_mutation_target": hard_moat_target.get("weekly_mutation_target"),
    "real_model_pool_audit_status": pool_audit.get("status"),
    "real_model_pool_existing_file_ratio": pool_audit.get("existing_file_ratio"),
    "real_model_pool_nontrivial_model_ratio": pool_audit.get("nontrivial_model_ratio"),
    "real_model_family_coverage_status": family_board.get("status"),
    "real_model_family_coverage_count": family_board.get("covered_families"),
    "real_model_family_entropy": family_board.get("family_entropy"),
    "real_model_source_diversity_guard_status": source_diversity_guard.get("status"),
    "real_model_source_diversity_unique_source_repos": source_diversity_guard.get("unique_source_repos"),
    "real_model_source_diversity_unique_source_buckets": source_diversity_guard.get("unique_source_buckets"),
    "real_model_source_diversity_max_source_bucket_share_pct": source_diversity_guard.get("max_source_bucket_share_pct"),
    "real_model_source_diversity_history_status": source_diversity_history.get("status"),
    "real_model_source_diversity_history_total_records": source_diversity_history.get("total_records"),
    "real_model_source_diversity_history_latest_unique_source_buckets": source_diversity_history.get("latest_unique_source_buckets"),
    "real_model_source_diversity_history_latest_max_source_bucket_share_pct": source_diversity_history.get("latest_max_source_bucket_share_pct"),
    "real_model_source_diversity_history_trend_status": source_diversity_history_trend.get("status"),
    "real_model_source_diversity_history_trend_delta_unique_source_buckets": (source_diversity_history_trend.get("trend") or {}).get("delta_unique_source_buckets"),
    "real_model_source_diversity_history_trend_delta_max_source_bucket_share_pct": (source_diversity_history_trend.get("trend") or {}).get("delta_max_source_bucket_share_pct"),
    "joint_moat_strength_status": joint_moat_strength.get("status"),
    "joint_moat_strength_score": joint_moat_strength.get("moat_strength_score"),
    "joint_moat_strength_grade": joint_moat_strength.get("moat_strength_grade"),
    "joint_moat_strength_hard_fail_count": joint_moat_strength.get("hard_fail_count"),
    "joint_moat_strength_history_status": joint_moat_strength_history.get("status"),
    "joint_moat_strength_history_total_records": joint_moat_strength_history.get("total_records"),
    "joint_moat_strength_history_latest_score": joint_moat_strength_history.get("latest_moat_strength_score"),
    "joint_moat_strength_history_trend_status": joint_moat_strength_history_trend.get("status"),
    "joint_moat_strength_history_trend_delta_score": (joint_moat_strength_history_trend.get("trend") or {}).get("delta_moat_strength_score"),
    "mutation_signature_uniqueness_status": mutation_signature_uniqueness.get("status"),
    "mutation_signature_uniqueness_total_mutations": mutation_signature_uniqueness.get("total_mutations"),
    "mutation_signature_uniqueness_unique_signatures": mutation_signature_uniqueness.get("unique_signatures"),
    "mutation_signature_uniqueness_unique_signature_ratio_pct": mutation_signature_uniqueness.get("unique_signature_ratio_pct"),
    "mutation_signature_uniqueness_duplicate_signatures": mutation_signature_uniqueness.get("duplicate_signatures"),
    "mutation_signature_uniqueness_history_status": mutation_signature_uniqueness_history.get("status"),
    "mutation_signature_uniqueness_history_total_records": mutation_signature_uniqueness_history.get("total_records"),
    "mutation_signature_uniqueness_history_latest_unique_signature_ratio_pct": mutation_signature_uniqueness_history.get("latest_unique_signature_ratio_pct"),
    "mutation_signature_uniqueness_history_trend_status": mutation_signature_uniqueness_history_trend.get("status"),
    "mutation_signature_uniqueness_history_trend_delta_unique_signature_ratio_pct": (mutation_signature_uniqueness_history_trend.get("trend") or {}).get("delta_unique_signature_ratio_pct"),
    "mutation_effective_scale_status": mutation_effective_scale.get("status"),
    "mutation_effective_scale_authenticity_multiplier": mutation_effective_scale.get("authenticity_multiplier"),
    "mutation_effective_scale_effective_reproducible_mutations": mutation_effective_scale.get("effective_reproducible_mutations"),
    "mutation_effective_scale_effective_vs_generated_ratio_pct": mutation_effective_scale.get("effective_vs_generated_ratio_pct"),
    "mutation_effective_scale_history_status": mutation_effective_scale_history.get("status"),
    "mutation_effective_scale_history_total_records": mutation_effective_scale_history.get("total_records"),
    "mutation_effective_scale_history_latest_effective_reproducible_mutations": mutation_effective_scale_history.get("latest_effective_reproducible_mutations"),
    "mutation_effective_scale_history_latest_authenticity_multiplier": mutation_effective_scale_history.get("latest_authenticity_multiplier"),
    "mutation_effective_scale_history_trend_status": mutation_effective_scale_history_trend.get("status"),
    "mutation_effective_scale_history_trend_delta_effective_reproducible_mutations": (mutation_effective_scale_history_trend.get("trend") or {}).get("delta_effective_reproducible_mutations"),
    "mutation_effective_scale_history_trend_delta_authenticity_multiplier": (mutation_effective_scale_history_trend.get("trend") or {}).get("delta_authenticity_multiplier"),
    "mutation_effective_depth_status": mutation_effective_depth.get("status"),
    "mutation_effective_depth_tracked_models": mutation_effective_depth.get("tracked_models"),
    "mutation_effective_depth_total_effective_mutations": mutation_effective_depth.get("total_effective_mutations"),
    "mutation_effective_depth_p10_effective_mutations_per_model": mutation_effective_depth.get("p10_effective_mutations_per_model"),
    "mutation_effective_depth_large_models_meeting_effective_depth_ratio_pct": mutation_effective_depth.get("large_models_meeting_effective_depth_ratio_pct"),
    "mutation_effective_depth_history_status": mutation_effective_depth_history.get("status"),
    "mutation_effective_depth_history_total_records": mutation_effective_depth_history.get("total_records"),
    "mutation_effective_depth_history_latest_total_effective_mutations": mutation_effective_depth_history.get("latest_total_effective_mutations"),
    "mutation_effective_depth_history_latest_p10_effective_mutations_per_model": mutation_effective_depth_history.get("latest_p10_effective_mutations_per_model"),
    "mutation_effective_depth_history_trend_status": mutation_effective_depth_history_trend.get("status"),
    "mutation_effective_depth_history_trend_delta_total_effective_mutations": (mutation_effective_depth_history_trend.get("trend") or {}).get("delta_total_effective_mutations"),
    "mutation_effective_depth_history_trend_delta_p10_effective_mutations_per_model": (mutation_effective_depth_history_trend.get("trend") or {}).get("delta_p10_effective_mutations_per_model"),
    "mutation_source_provenance_status": mutation_source_provenance.get("status"),
    "mutation_source_provenance_with_source_path_count": mutation_source_provenance.get("with_source_path_count"),
    "mutation_source_provenance_existing_source_path_ratio_pct": mutation_source_provenance.get("existing_source_path_ratio_pct"),
    "mutation_source_provenance_allowed_root_ratio_pct": mutation_source_provenance.get("allowed_root_ratio_pct"),
    "mutation_source_provenance_registry_match_ratio_pct": mutation_source_provenance.get("registry_match_ratio_pct"),
    "mutation_source_provenance_history_status": mutation_source_provenance_history.get("status"),
    "mutation_source_provenance_history_total_records": mutation_source_provenance_history.get("total_records"),
    "mutation_source_provenance_history_latest_existing_source_path_ratio_pct": mutation_source_provenance_history.get("latest_existing_source_path_ratio_pct"),
    "mutation_source_provenance_history_latest_allowed_root_ratio_pct": mutation_source_provenance_history.get("latest_allowed_root_ratio_pct"),
    "mutation_source_provenance_history_trend_status": mutation_source_provenance_history_trend.get("status"),
    "mutation_source_provenance_history_trend_delta_existing_source_path_ratio_pct": (mutation_source_provenance_history_trend.get("trend") or {}).get("delta_existing_source_path_ratio_pct"),
    "mutation_source_provenance_history_trend_delta_allowed_root_ratio_pct": (mutation_source_provenance_history_trend.get("trend") or {}).get("delta_allowed_root_ratio_pct"),
    "mutation_authentic_scale_score_status": mutation_authentic_scale_score.get("status"),
    "mutation_authentic_scale_score": mutation_authentic_scale_score.get("authentic_scale_score"),
    "mutation_authentic_scale_grade": mutation_authentic_scale_score.get("authentic_scale_grade"),
    "mutation_authentic_scale_score_history_status": mutation_authentic_scale_score_history.get("status"),
    "mutation_authentic_scale_score_history_total_records": mutation_authentic_scale_score_history.get("total_records"),
    "mutation_authentic_scale_score_history_latest_score": mutation_authentic_scale_score_history.get("latest_authentic_scale_score"),
    "mutation_authentic_scale_score_history_trend_status": mutation_authentic_scale_score_history_trend.get("status"),
    "mutation_authentic_scale_score_history_trend_delta_score": (mutation_authentic_scale_score_history_trend.get("trend") or {}).get("delta_authentic_scale_score"),
    "mutation_source_bucket_effective_scale_status": mutation_source_bucket_effective_scale.get("status"),
    "mutation_source_bucket_effective_scale_bucket_count": mutation_source_bucket_effective_scale.get("source_bucket_count"),
    "mutation_source_bucket_effective_scale_effective_mutations": mutation_source_bucket_effective_scale.get("effective_mutations"),
    "mutation_source_bucket_effective_scale_max_bucket_share_pct": mutation_source_bucket_effective_scale.get("max_bucket_share_pct"),
    "mutation_source_bucket_effective_scale_history_status": mutation_source_bucket_effective_scale_history.get("status"),
    "mutation_source_bucket_effective_scale_history_total_records": mutation_source_bucket_effective_scale_history.get("total_records"),
    "mutation_source_bucket_effective_scale_history_latest_bucket_count": mutation_source_bucket_effective_scale_history.get("latest_source_bucket_count"),
    "mutation_source_bucket_effective_scale_history_trend_status": mutation_source_bucket_effective_scale_history_trend.get("status"),
    "mutation_source_bucket_effective_scale_history_trend_delta_bucket_count": (mutation_source_bucket_effective_scale_history_trend.get("trend") or {}).get("delta_source_bucket_count"),
    "mutation_artifact_inventory_status": mutation_inventory.get("status"),
    "mutation_artifact_existing_file_ratio": mutation_inventory.get("existing_file_ratio"),
    "mutation_artifact_execution_coverage_ratio": mutation_inventory.get("execution_coverage_ratio"),
    "asset_locator_manifest_status": asset_locator.get("status"),
    "asset_locator_model_root_count": asset_locator.get("model_root_count"),
    "asset_locator_mutant_root_count": asset_locator.get("mutant_root_count"),
    "reproducible_sample_pack_status": repro_sample_pack.get("status"),
    "reproducible_sample_pack_sampled_mutations": repro_sample_pack.get("sampled_mutations"),
    "scale_evidence_stamp_status": evidence_stamp.get("status"),
    "scale_evidence_stamp_score": evidence_stamp.get("evidence_score"),
    "scale_evidence_stamp_grade": evidence_stamp.get("evidence_grade"),
    "reproducible_mutations": realrun.get("executed_count"),
    "mutation_execution_authenticity_status": mutation_exec_auth.get("status"),
    "mutation_execution_authenticity_solver_command_ratio_pct": mutation_exec_auth.get("solver_command_ratio_pct"),
    "mutation_execution_authenticity_probe_only_command_ratio_pct": mutation_exec_auth.get("probe_only_command_ratio_pct"),
    "mutation_execution_authenticity_placeholder_executed_ratio_pct": mutation_exec_auth.get("placeholder_executed_ratio_pct"),
    "mutation_execution_authenticity_failure_signal_ratio_pct": mutation_exec_auth.get("failure_signal_ratio_pct"),
    "mutation_execution_authenticity_history_status": mutation_exec_auth_history.get("status"),
    "mutation_execution_authenticity_history_total_records": mutation_exec_auth_history.get("total_records"),
    "mutation_execution_authenticity_history_latest_solver_command_ratio_pct": mutation_exec_auth_history.get("latest_solver_command_ratio_pct"),
    "mutation_execution_authenticity_history_latest_probe_only_command_ratio_pct": mutation_exec_auth_history.get("latest_probe_only_command_ratio_pct"),
    "mutation_execution_authenticity_history_trend_status": mutation_exec_auth_history_trend.get("status"),
    "mutation_execution_authenticity_history_trend_delta_solver_command_ratio_pct": (mutation_exec_auth_history_trend.get("trend") or {}).get("delta_solver_command_ratio_pct"),
    "mutation_execution_authenticity_history_trend_delta_probe_only_command_ratio_pct": (mutation_exec_auth_history_trend.get("trend") or {}).get("delta_probe_only_command_ratio_pct"),
    "mutation_failure_signal_authenticity_status": mutation_failure_signal_auth.get("status"),
    "mutation_failure_signal_authenticity_failure_signal_ratio_pct": mutation_failure_signal_auth.get("failure_signal_ratio_pct"),
    "mutation_failure_signal_authenticity_expected_failure_type_signal_coverage_pct": mutation_failure_signal_auth.get("expected_failure_type_signal_coverage_pct"),
    "mutation_failure_signal_authenticity_observed_coverage_ratio_pct": mutation_failure_signal_auth.get("observed_coverage_ratio_pct"),
    "mutation_failure_signal_authenticity_history_status": mutation_failure_signal_auth_history.get("status"),
    "mutation_failure_signal_authenticity_history_total_records": mutation_failure_signal_auth_history.get("total_records"),
    "mutation_failure_signal_authenticity_history_latest_failure_signal_ratio_pct": mutation_failure_signal_auth_history.get("latest_failure_signal_ratio_pct"),
    "mutation_failure_signal_authenticity_history_latest_expected_failure_type_signal_coverage_pct": mutation_failure_signal_auth_history.get("latest_expected_failure_type_signal_coverage_pct"),
    "mutation_failure_signal_authenticity_history_trend_status": mutation_failure_signal_auth_history_trend.get("status"),
    "mutation_failure_signal_authenticity_history_trend_delta_failure_signal_ratio_pct": (mutation_failure_signal_auth_history_trend.get("trend") or {}).get("delta_failure_signal_ratio_pct"),
    "mutation_failure_signal_authenticity_history_trend_delta_expected_failure_type_signal_coverage_pct": (mutation_failure_signal_auth_history_trend.get("trend") or {}).get("delta_expected_failure_type_signal_coverage_pct"),
    "large_model_executable_truth_status": large_model_truth.get("status"),
    "large_model_executable_truth_large_model_count": large_model_truth.get("large_model_count"),
    "large_model_executable_truth_large_executable_real_count": large_model_truth.get("large_executable_real_count"),
    "large_model_executable_truth_large_executable_real_rate_pct": large_model_truth.get("large_executable_real_rate_pct"),
    "large_model_executable_truth_history_status": large_model_truth_history.get("status"),
    "large_model_executable_truth_history_total_records": large_model_truth_history.get("total_records"),
    "large_model_executable_truth_history_latest_large_executable_real_count": large_model_truth_history.get("latest_large_executable_real_count"),
    "large_model_executable_truth_history_latest_large_executable_real_rate_pct": large_model_truth_history.get("latest_large_executable_real_rate_pct"),
    "large_model_executable_truth_history_trend_status": large_model_truth_history_trend.get("status"),
    "large_model_executable_truth_history_trend_delta_large_executable_real_count": (large_model_truth_history_trend.get("trend") or {}).get("delta_large_executable_real_count"),
    "large_model_executable_truth_history_trend_delta_large_executable_real_rate_pct": (large_model_truth_history_trend.get("trend") or {}).get("delta_large_executable_real_rate_pct"),
    "large_model_authenticity_status": large_model_authenticity.get("status"),
    "large_model_authenticity_score": large_model_authenticity.get("large_model_authenticity_score"),
    "large_model_authenticity_failed_gate_count": large_model_authenticity.get("failed_gate_count"),
    "large_model_authenticity_history_status": large_model_authenticity_history.get("status"),
    "large_model_authenticity_history_total_records": large_model_authenticity_history.get("total_records"),
    "large_model_authenticity_history_latest_score": large_model_authenticity_history.get("latest_large_model_authenticity_score"),
    "large_model_authenticity_history_trend_status": large_model_authenticity_history_trend.get("status"),
    "large_model_authenticity_history_trend_delta_score": (large_model_authenticity_history_trend.get("trend") or {}).get("delta_large_model_authenticity_score"),
    "moat_weekly_target_gate_status": moat_weekly_target_gate.get("status"),
    "moat_weekly_target_weekly_target_status": moat_weekly_target_gate.get("weekly_target_status"),
    "moat_weekly_target_gap_count": len(moat_weekly_target_gate.get("target_gaps") or []),
    "hard_moat_gates_status": hard_moat.get("status"),
    "hard_moat_hardness_score": hard_moat.get("moat_hardness_score"),
    "hard_moat_failed_gate_count": hard_moat.get("failed_gate_count"),
    "hard_moat_critical_failed_gate_count": hard_moat.get("critical_failed_gate_count"),
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
            f"- raw_models: `{summary['raw_models']}`",
            f"- executable_unique_models: `{summary['executable_unique_models']}`",
            f"- executable_large_models: `{summary['executable_large_models']}`",
            f"- canonical_total_models: `{summary['canonical_total_models']}`",
            f"- canonical_new_models: `{summary['canonical_new_models']}`",
            f"- canonical_net_growth_models: `{summary['canonical_net_growth_models']}`",
            f"- canonical_new_large_models: `{summary['canonical_new_large_models']}`",
            f"- real_model_net_growth_authenticity_status: `{summary['real_model_net_growth_authenticity_status']}`",
            f"- real_model_net_growth_authenticity_net_new_unique_models: `{summary['real_model_net_growth_authenticity_net_new_unique_models']}`",
            f"- real_model_net_growth_authenticity_true_growth_ratio_pct: `{summary['real_model_net_growth_authenticity_true_growth_ratio_pct']}`",
            f"- real_model_net_growth_authenticity_suspected_duplicate_ratio_pct: `{summary['real_model_net_growth_authenticity_suspected_duplicate_ratio_pct']}`",
            f"- real_model_net_growth_authenticity_history_status: `{summary['real_model_net_growth_authenticity_history_status']}`",
            f"- real_model_net_growth_authenticity_history_total_records: `{summary['real_model_net_growth_authenticity_history_total_records']}`",
            f"- real_model_net_growth_authenticity_history_latest_net_new_unique_models: `{summary['real_model_net_growth_authenticity_history_latest_net_new_unique_models']}`",
            f"- real_model_net_growth_authenticity_history_latest_true_growth_ratio_pct: `{summary['real_model_net_growth_authenticity_history_latest_true_growth_ratio_pct']}`",
            f"- real_model_net_growth_authenticity_history_trend_status: `{summary['real_model_net_growth_authenticity_history_trend_status']}`",
            f"- real_model_net_growth_authenticity_history_trend_delta_net_new_unique_models: `{summary['real_model_net_growth_authenticity_history_trend_delta_net_new_unique_models']}`",
            f"- real_model_net_growth_authenticity_history_trend_delta_true_growth_ratio_pct: `{summary['real_model_net_growth_authenticity_history_trend_delta_true_growth_ratio_pct']}`",
            f"- mutation_recipe_library_v2_status: `{summary['mutation_recipe_library_v2_status']}`",
            f"- mutation_recipe_total_recipes: `{summary['mutation_recipe_total_recipes']}`",
            f"- mutation_recipe_operator_family_count: `{summary['mutation_recipe_operator_family_count']}`",
            f"- mutation_selection_plan_status: `{summary['mutation_selection_plan_status']}`",
            f"- mutation_selection_plan_selected_models: `{summary['mutation_selection_plan_selected_models']}`",
            f"- mutation_selection_plan_selected_large_ratio_pct: `{summary['mutation_selection_plan_selected_large_ratio_pct']}`",
            f"- mutation_selection_plan_selected_families: `{summary['mutation_selection_plan_selected_families']}`",
            f"- mutation_selection_plan_selected_source_buckets: `{summary['mutation_selection_plan_selected_source_buckets']}`",
            f"- mutation_selection_balance_guard_status: `{summary['mutation_selection_balance_guard_status']}`",
            f"- mutation_selection_balance_guard_max_family_share_pct: `{summary['mutation_selection_balance_guard_max_family_share_pct']}`",
            f"- mutation_selection_history_status: `{summary['mutation_selection_history_status']}`",
            f"- mutation_selection_history_total_records: `{summary['mutation_selection_history_total_records']}`",
            f"- mutation_selection_history_latest_selected_large_ratio_pct: `{summary['mutation_selection_history_latest_selected_large_ratio_pct']}`",
            f"- mutation_selection_history_latest_max_family_share_pct: `{summary['mutation_selection_history_latest_max_family_share_pct']}`",
            f"- mutation_selection_history_trend_status: `{summary['mutation_selection_history_trend_status']}`",
            f"- mutation_selection_history_trend_delta_selected_large_ratio_pct: `{summary['mutation_selection_history_trend_delta_selected_large_ratio_pct']}`",
            f"- mutation_selection_history_trend_delta_selected_family_coverage: `{summary['mutation_selection_history_trend_delta_selected_family_coverage']}`",
            f"- mutation_selection_history_trend_delta_max_family_share_pct: `{summary['mutation_selection_history_trend_delta_max_family_share_pct']}`",
            f"- mutation_repro_depth_guard_status: `{summary['mutation_repro_depth_guard_status']}`",
            f"- mutation_repro_depth_guard_tracked_models: `{summary['mutation_repro_depth_guard_tracked_models']}`",
            f"- mutation_repro_depth_guard_models_meeting_depth_ratio_pct: `{summary['mutation_repro_depth_guard_models_meeting_depth_ratio_pct']}`",
            f"- mutation_repro_depth_guard_p10_reproducible_mutations_per_model: `{summary['mutation_repro_depth_guard_p10_reproducible_mutations_per_model']}`",
            f"- mutation_repro_depth_guard_max_model_share_pct: `{summary['mutation_repro_depth_guard_max_model_share_pct']}`",
            f"- mutation_repro_depth_history_status: `{summary['mutation_repro_depth_history_status']}`",
            f"- mutation_repro_depth_history_total_records: `{summary['mutation_repro_depth_history_total_records']}`",
            f"- mutation_repro_depth_history_latest_depth_ratio_pct: `{summary['mutation_repro_depth_history_latest_depth_ratio_pct']}`",
            f"- mutation_repro_depth_history_latest_p10_depth: `{summary['mutation_repro_depth_history_latest_p10_depth']}`",
            f"- mutation_repro_depth_history_latest_concentration_pct: `{summary['mutation_repro_depth_history_latest_concentration_pct']}`",
            f"- mutation_repro_depth_history_trend_status: `{summary['mutation_repro_depth_history_trend_status']}`",
            f"- mutation_repro_depth_history_trend_delta_depth_ratio_pct: `{summary['mutation_repro_depth_history_trend_delta_depth_ratio_pct']}`",
            f"- mutation_repro_depth_history_trend_delta_p10_depth: `{summary['mutation_repro_depth_history_trend_delta_p10_depth']}`",
            f"- mutation_repro_depth_history_trend_delta_concentration_pct: `{summary['mutation_repro_depth_history_trend_delta_concentration_pct']}`",
            f"- generated_mutations: `{summary['generated_mutations']}`",
            f"- materialized_mutations: `{summary['materialized_mutations']}`",
            f"- mutation_validation_status: `{summary['mutation_validation_status']}`",
            f"- validation_backend_used: `{summary['validation_backend_used']}`",
            f"- baseline_check_pass_rate_pct: `{summary['baseline_check_pass_rate_pct']}`",
            f"- validation_stage_match_rate_pct: `{summary['validation_stage_match_rate_pct']}`",
            f"- validation_type_match_rate_pct: `{summary['validation_type_match_rate_pct']}`",
            f"- validation_v2_status: `{summary['validation_v2_status']}`",
            f"- validation_v2_medium_type_match_rate_pct: `{summary['validation_v2_medium_type_match_rate_pct']}`",
            f"- validation_v2_large_type_match_rate_pct: `{summary['validation_v2_large_type_match_rate_pct']}`",
            f"- failure_distribution_guard_status: `{summary['failure_distribution_guard_status']}`",
            f"- failure_distribution_guard_entropy: `{summary['failure_distribution_guard_entropy']}`",
            f"- failure_distribution_guard_drift_tvd: `{summary['failure_distribution_guard_drift_tvd']}`",
            f"- mismatch_triage_status: `{summary['mismatch_triage_status']}`",
            f"- mismatch_triage_count: `{summary['mismatch_triage_count']}`",
            f"- coverage_backfill_status: `{summary['coverage_backfill_status']}`",
            f"- coverage_backfill_total_tasks: `{summary['coverage_backfill_total_tasks']}`",
            f"- coverage_backfill_p0_tasks: `{summary['coverage_backfill_p0_tasks']}`",
            f"- failure_type_balance_status: `{summary['failure_type_balance_status']}`",
            f"- failure_type_balance_expected_count: `{summary['failure_type_balance_expected_count']}`",
            f"- failure_type_balance_expected_entropy: `{summary['failure_type_balance_expected_entropy']}`",
            f"- ingest_source_channel_planner_status: `{summary['ingest_source_channel_planner_status']}`",
            f"- ingest_source_channel_planner_p0_channels: `{summary['ingest_source_channel_planner_p0_channels']}`",
            f"- ingest_source_channel_planner_planned_weekly_new_models: `{summary['ingest_source_channel_planner_planned_weekly_new_models']}`",
            f"- hard_moat_target_profile_status: `{summary['hard_moat_target_profile_status']}`",
            f"- hard_moat_target_profile_strictness_level: `{summary['hard_moat_target_profile_strictness_level']}`",
            f"- hard_moat_target_profile_weekly_model_target: `{summary['hard_moat_target_profile_weekly_model_target']}`",
            f"- hard_moat_target_profile_weekly_mutation_target: `{summary['hard_moat_target_profile_weekly_mutation_target']}`",
            f"- real_model_pool_audit_status: `{summary['real_model_pool_audit_status']}`",
            f"- real_model_pool_existing_file_ratio: `{summary['real_model_pool_existing_file_ratio']}`",
            f"- real_model_pool_nontrivial_model_ratio: `{summary['real_model_pool_nontrivial_model_ratio']}`",
            f"- real_model_family_coverage_status: `{summary['real_model_family_coverage_status']}`",
            f"- real_model_family_coverage_count: `{summary['real_model_family_coverage_count']}`",
            f"- real_model_family_entropy: `{summary['real_model_family_entropy']}`",
            f"- real_model_source_diversity_guard_status: `{summary['real_model_source_diversity_guard_status']}`",
            f"- real_model_source_diversity_unique_source_repos: `{summary['real_model_source_diversity_unique_source_repos']}`",
            f"- real_model_source_diversity_unique_source_buckets: `{summary['real_model_source_diversity_unique_source_buckets']}`",
            f"- real_model_source_diversity_max_source_bucket_share_pct: `{summary['real_model_source_diversity_max_source_bucket_share_pct']}`",
            f"- real_model_source_diversity_history_status: `{summary['real_model_source_diversity_history_status']}`",
            f"- real_model_source_diversity_history_total_records: `{summary['real_model_source_diversity_history_total_records']}`",
            f"- real_model_source_diversity_history_latest_unique_source_buckets: `{summary['real_model_source_diversity_history_latest_unique_source_buckets']}`",
            f"- real_model_source_diversity_history_latest_max_source_bucket_share_pct: `{summary['real_model_source_diversity_history_latest_max_source_bucket_share_pct']}`",
            f"- real_model_source_diversity_history_trend_status: `{summary['real_model_source_diversity_history_trend_status']}`",
            f"- real_model_source_diversity_history_trend_delta_unique_source_buckets: `{summary['real_model_source_diversity_history_trend_delta_unique_source_buckets']}`",
            f"- real_model_source_diversity_history_trend_delta_max_source_bucket_share_pct: `{summary['real_model_source_diversity_history_trend_delta_max_source_bucket_share_pct']}`",
            f"- joint_moat_strength_status: `{summary['joint_moat_strength_status']}`",
            f"- joint_moat_strength_score: `{summary['joint_moat_strength_score']}`",
            f"- joint_moat_strength_grade: `{summary['joint_moat_strength_grade']}`",
            f"- joint_moat_strength_hard_fail_count: `{summary['joint_moat_strength_hard_fail_count']}`",
            f"- joint_moat_strength_history_status: `{summary['joint_moat_strength_history_status']}`",
            f"- joint_moat_strength_history_total_records: `{summary['joint_moat_strength_history_total_records']}`",
            f"- joint_moat_strength_history_latest_score: `{summary['joint_moat_strength_history_latest_score']}`",
            f"- joint_moat_strength_history_trend_status: `{summary['joint_moat_strength_history_trend_status']}`",
            f"- joint_moat_strength_history_trend_delta_score: `{summary['joint_moat_strength_history_trend_delta_score']}`",
            f"- mutation_signature_uniqueness_status: `{summary['mutation_signature_uniqueness_status']}`",
            f"- mutation_signature_uniqueness_total_mutations: `{summary['mutation_signature_uniqueness_total_mutations']}`",
            f"- mutation_signature_uniqueness_unique_signatures: `{summary['mutation_signature_uniqueness_unique_signatures']}`",
            f"- mutation_signature_uniqueness_unique_signature_ratio_pct: `{summary['mutation_signature_uniqueness_unique_signature_ratio_pct']}`",
            f"- mutation_signature_uniqueness_duplicate_signatures: `{summary['mutation_signature_uniqueness_duplicate_signatures']}`",
            f"- mutation_signature_uniqueness_history_status: `{summary['mutation_signature_uniqueness_history_status']}`",
            f"- mutation_signature_uniqueness_history_total_records: `{summary['mutation_signature_uniqueness_history_total_records']}`",
            f"- mutation_signature_uniqueness_history_latest_unique_signature_ratio_pct: `{summary['mutation_signature_uniqueness_history_latest_unique_signature_ratio_pct']}`",
            f"- mutation_signature_uniqueness_history_trend_status: `{summary['mutation_signature_uniqueness_history_trend_status']}`",
            f"- mutation_signature_uniqueness_history_trend_delta_unique_signature_ratio_pct: `{summary['mutation_signature_uniqueness_history_trend_delta_unique_signature_ratio_pct']}`",
            f"- mutation_effective_scale_status: `{summary['mutation_effective_scale_status']}`",
            f"- mutation_effective_scale_authenticity_multiplier: `{summary['mutation_effective_scale_authenticity_multiplier']}`",
            f"- mutation_effective_scale_effective_reproducible_mutations: `{summary['mutation_effective_scale_effective_reproducible_mutations']}`",
            f"- mutation_effective_scale_effective_vs_generated_ratio_pct: `{summary['mutation_effective_scale_effective_vs_generated_ratio_pct']}`",
            f"- mutation_effective_scale_history_status: `{summary['mutation_effective_scale_history_status']}`",
            f"- mutation_effective_scale_history_total_records: `{summary['mutation_effective_scale_history_total_records']}`",
            f"- mutation_effective_scale_history_latest_effective_reproducible_mutations: `{summary['mutation_effective_scale_history_latest_effective_reproducible_mutations']}`",
            f"- mutation_effective_scale_history_latest_authenticity_multiplier: `{summary['mutation_effective_scale_history_latest_authenticity_multiplier']}`",
            f"- mutation_effective_scale_history_trend_status: `{summary['mutation_effective_scale_history_trend_status']}`",
            f"- mutation_effective_scale_history_trend_delta_effective_reproducible_mutations: `{summary['mutation_effective_scale_history_trend_delta_effective_reproducible_mutations']}`",
            f"- mutation_effective_scale_history_trend_delta_authenticity_multiplier: `{summary['mutation_effective_scale_history_trend_delta_authenticity_multiplier']}`",
            f"- mutation_effective_depth_status: `{summary['mutation_effective_depth_status']}`",
            f"- mutation_effective_depth_tracked_models: `{summary['mutation_effective_depth_tracked_models']}`",
            f"- mutation_effective_depth_total_effective_mutations: `{summary['mutation_effective_depth_total_effective_mutations']}`",
            f"- mutation_effective_depth_p10_effective_mutations_per_model: `{summary['mutation_effective_depth_p10_effective_mutations_per_model']}`",
            f"- mutation_effective_depth_large_models_meeting_effective_depth_ratio_pct: `{summary['mutation_effective_depth_large_models_meeting_effective_depth_ratio_pct']}`",
            f"- mutation_effective_depth_history_status: `{summary['mutation_effective_depth_history_status']}`",
            f"- mutation_effective_depth_history_total_records: `{summary['mutation_effective_depth_history_total_records']}`",
            f"- mutation_effective_depth_history_latest_total_effective_mutations: `{summary['mutation_effective_depth_history_latest_total_effective_mutations']}`",
            f"- mutation_effective_depth_history_latest_p10_effective_mutations_per_model: `{summary['mutation_effective_depth_history_latest_p10_effective_mutations_per_model']}`",
            f"- mutation_effective_depth_history_trend_status: `{summary['mutation_effective_depth_history_trend_status']}`",
            f"- mutation_effective_depth_history_trend_delta_total_effective_mutations: `{summary['mutation_effective_depth_history_trend_delta_total_effective_mutations']}`",
            f"- mutation_effective_depth_history_trend_delta_p10_effective_mutations_per_model: `{summary['mutation_effective_depth_history_trend_delta_p10_effective_mutations_per_model']}`",
            f"- mutation_source_provenance_status: `{summary['mutation_source_provenance_status']}`",
            f"- mutation_source_provenance_with_source_path_count: `{summary['mutation_source_provenance_with_source_path_count']}`",
            f"- mutation_source_provenance_existing_source_path_ratio_pct: `{summary['mutation_source_provenance_existing_source_path_ratio_pct']}`",
            f"- mutation_source_provenance_allowed_root_ratio_pct: `{summary['mutation_source_provenance_allowed_root_ratio_pct']}`",
            f"- mutation_source_provenance_registry_match_ratio_pct: `{summary['mutation_source_provenance_registry_match_ratio_pct']}`",
            f"- mutation_source_provenance_history_status: `{summary['mutation_source_provenance_history_status']}`",
            f"- mutation_source_provenance_history_total_records: `{summary['mutation_source_provenance_history_total_records']}`",
            f"- mutation_source_provenance_history_latest_existing_source_path_ratio_pct: `{summary['mutation_source_provenance_history_latest_existing_source_path_ratio_pct']}`",
            f"- mutation_source_provenance_history_latest_allowed_root_ratio_pct: `{summary['mutation_source_provenance_history_latest_allowed_root_ratio_pct']}`",
            f"- mutation_source_provenance_history_trend_status: `{summary['mutation_source_provenance_history_trend_status']}`",
            f"- mutation_source_provenance_history_trend_delta_existing_source_path_ratio_pct: `{summary['mutation_source_provenance_history_trend_delta_existing_source_path_ratio_pct']}`",
            f"- mutation_source_provenance_history_trend_delta_allowed_root_ratio_pct: `{summary['mutation_source_provenance_history_trend_delta_allowed_root_ratio_pct']}`",
            f"- mutation_artifact_inventory_status: `{summary['mutation_artifact_inventory_status']}`",
            f"- mutation_artifact_existing_file_ratio: `{summary['mutation_artifact_existing_file_ratio']}`",
            f"- mutation_artifact_execution_coverage_ratio: `{summary['mutation_artifact_execution_coverage_ratio']}`",
            f"- asset_locator_manifest_status: `{summary['asset_locator_manifest_status']}`",
            f"- asset_locator_model_root_count: `{summary['asset_locator_model_root_count']}`",
            f"- asset_locator_mutant_root_count: `{summary['asset_locator_mutant_root_count']}`",
            f"- reproducible_sample_pack_status: `{summary['reproducible_sample_pack_status']}`",
            f"- reproducible_sample_pack_sampled_mutations: `{summary['reproducible_sample_pack_sampled_mutations']}`",
            f"- scale_evidence_stamp_status: `{summary['scale_evidence_stamp_status']}`",
            f"- scale_evidence_stamp_score: `{summary['scale_evidence_stamp_score']}`",
            f"- scale_evidence_stamp_grade: `{summary['scale_evidence_stamp_grade']}`",
            f"- reproducible_mutations: `{summary['reproducible_mutations']}`",
            f"- mutation_execution_authenticity_status: `{summary['mutation_execution_authenticity_status']}`",
            f"- mutation_execution_authenticity_solver_command_ratio_pct: `{summary['mutation_execution_authenticity_solver_command_ratio_pct']}`",
            f"- mutation_execution_authenticity_probe_only_command_ratio_pct: `{summary['mutation_execution_authenticity_probe_only_command_ratio_pct']}`",
            f"- mutation_execution_authenticity_placeholder_executed_ratio_pct: `{summary['mutation_execution_authenticity_placeholder_executed_ratio_pct']}`",
            f"- mutation_execution_authenticity_failure_signal_ratio_pct: `{summary['mutation_execution_authenticity_failure_signal_ratio_pct']}`",
            f"- mutation_execution_authenticity_history_status: `{summary['mutation_execution_authenticity_history_status']}`",
            f"- mutation_execution_authenticity_history_total_records: `{summary['mutation_execution_authenticity_history_total_records']}`",
            f"- mutation_execution_authenticity_history_latest_solver_command_ratio_pct: `{summary['mutation_execution_authenticity_history_latest_solver_command_ratio_pct']}`",
            f"- mutation_execution_authenticity_history_latest_probe_only_command_ratio_pct: `{summary['mutation_execution_authenticity_history_latest_probe_only_command_ratio_pct']}`",
            f"- mutation_execution_authenticity_history_trend_status: `{summary['mutation_execution_authenticity_history_trend_status']}`",
            f"- mutation_execution_authenticity_history_trend_delta_solver_command_ratio_pct: `{summary['mutation_execution_authenticity_history_trend_delta_solver_command_ratio_pct']}`",
            f"- mutation_execution_authenticity_history_trend_delta_probe_only_command_ratio_pct: `{summary['mutation_execution_authenticity_history_trend_delta_probe_only_command_ratio_pct']}`",
            f"- mutation_failure_signal_authenticity_status: `{summary['mutation_failure_signal_authenticity_status']}`",
            f"- mutation_failure_signal_authenticity_failure_signal_ratio_pct: `{summary['mutation_failure_signal_authenticity_failure_signal_ratio_pct']}`",
            f"- mutation_failure_signal_authenticity_expected_failure_type_signal_coverage_pct: `{summary['mutation_failure_signal_authenticity_expected_failure_type_signal_coverage_pct']}`",
            f"- mutation_failure_signal_authenticity_observed_coverage_ratio_pct: `{summary['mutation_failure_signal_authenticity_observed_coverage_ratio_pct']}`",
            f"- mutation_failure_signal_authenticity_history_status: `{summary['mutation_failure_signal_authenticity_history_status']}`",
            f"- mutation_failure_signal_authenticity_history_total_records: `{summary['mutation_failure_signal_authenticity_history_total_records']}`",
            f"- mutation_failure_signal_authenticity_history_latest_failure_signal_ratio_pct: `{summary['mutation_failure_signal_authenticity_history_latest_failure_signal_ratio_pct']}`",
            f"- mutation_failure_signal_authenticity_history_latest_expected_failure_type_signal_coverage_pct: `{summary['mutation_failure_signal_authenticity_history_latest_expected_failure_type_signal_coverage_pct']}`",
            f"- mutation_failure_signal_authenticity_history_trend_status: `{summary['mutation_failure_signal_authenticity_history_trend_status']}`",
            f"- mutation_failure_signal_authenticity_history_trend_delta_failure_signal_ratio_pct: `{summary['mutation_failure_signal_authenticity_history_trend_delta_failure_signal_ratio_pct']}`",
            f"- mutation_failure_signal_authenticity_history_trend_delta_expected_failure_type_signal_coverage_pct: `{summary['mutation_failure_signal_authenticity_history_trend_delta_expected_failure_type_signal_coverage_pct']}`",
            f"- large_model_executable_truth_status: `{summary['large_model_executable_truth_status']}`",
            f"- large_model_executable_truth_large_model_count: `{summary['large_model_executable_truth_large_model_count']}`",
            f"- large_model_executable_truth_large_executable_real_count: `{summary['large_model_executable_truth_large_executable_real_count']}`",
            f"- large_model_executable_truth_large_executable_real_rate_pct: `{summary['large_model_executable_truth_large_executable_real_rate_pct']}`",
            f"- large_model_executable_truth_history_status: `{summary['large_model_executable_truth_history_status']}`",
            f"- large_model_executable_truth_history_total_records: `{summary['large_model_executable_truth_history_total_records']}`",
            f"- large_model_executable_truth_history_latest_large_executable_real_count: `{summary['large_model_executable_truth_history_latest_large_executable_real_count']}`",
            f"- large_model_executable_truth_history_latest_large_executable_real_rate_pct: `{summary['large_model_executable_truth_history_latest_large_executable_real_rate_pct']}`",
            f"- large_model_executable_truth_history_trend_status: `{summary['large_model_executable_truth_history_trend_status']}`",
            f"- large_model_executable_truth_history_trend_delta_large_executable_real_count: `{summary['large_model_executable_truth_history_trend_delta_large_executable_real_count']}`",
            f"- large_model_executable_truth_history_trend_delta_large_executable_real_rate_pct: `{summary['large_model_executable_truth_history_trend_delta_large_executable_real_rate_pct']}`",
            f"- hard_moat_gates_status: `{summary['hard_moat_gates_status']}`",
            f"- hard_moat_hardness_score: `{summary['hard_moat_hardness_score']}`",
            f"- hard_moat_failed_gate_count: `{summary['hard_moat_failed_gate_count']}`",
            f"- hard_moat_critical_failed_gate_count: `{summary['hard_moat_critical_failed_gate_count']}`",
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

python3 -m gateforge.dataset_scale_batch_history_ledger_v1 \
  --record "$OUT_DIR/summary.json" \
  --ledger "$SCALE_HISTORY_LEDGER_PATH" \
  --out "$OUT_DIR/scale_history_summary.json" \
  --report-out "$OUT_DIR/scale_history_summary.md"

python3 -m gateforge.dataset_scale_target_gap_v1 \
  --scale-batch-summary "$OUT_DIR/summary.json" \
  --scale-batch-history-summary "$OUT_DIR/scale_history_summary.json" \
  --target-model-pool-size "${GATEFORGE_TARGET_MODEL_POOL_SIZE:-8000}" \
  --target-reproducible-mutations "${GATEFORGE_TARGET_REPRO_MUTATIONS:-36000}" \
  --target-hardness-score "${GATEFORGE_TARGET_HARDNESS_SCORE:-85}" \
  --target-horizon-weeks "${GATEFORGE_TARGET_HORIZON_WEEKS:-12}" \
  --out "$OUT_DIR/scale_target_gap_summary.json" \
  --report-out "$OUT_DIR/scale_target_gap_summary.md"

python3 -m gateforge.dataset_scale_execution_priority_board_v1 \
  --scale-target-gap-summary "$OUT_DIR/scale_target_gap_summary.json" \
  --ingest-source-channel-planner-summary "$OUT_DIR/ingest_source_channel_planner_summary.json" \
  --hard-moat-gates-summary "$OUT_DIR/hard_moat_gates_summary.json" \
  --coverage-backfill-summary "$OUT_DIR/mutation_coverage_backfill_summary.json" \
  --out "$OUT_DIR/scale_execution_priority_board_summary.json" \
  --report-out "$OUT_DIR/scale_execution_priority_board_summary.md"

python3 -m gateforge.dataset_weekly_scale_milestone_checkpoint_v1 \
  --scale-batch-summary "$OUT_DIR/summary.json" \
  --scale-target-gap-summary "$OUT_DIR/scale_target_gap_summary.json" \
  --scale-evidence-stamp-summary "$OUT_DIR/scale_evidence_stamp_summary.json" \
  --real-model-family-coverage-board-summary "$OUT_DIR/real_model_family_coverage_board_summary.json" \
  --mutation-failure-type-balance-guard-summary "$OUT_DIR/mutation_failure_type_balance_guard_summary.json" \
  --scale-execution-priority-board-summary "$OUT_DIR/scale_execution_priority_board_summary.json" \
  --out "$OUT_DIR/weekly_scale_milestone_checkpoint_summary.json" \
  --report-out "$OUT_DIR/weekly_scale_milestone_checkpoint_summary.md"

python3 -m gateforge.dataset_scale_velocity_forecast_v1 \
  --scale-target-gap-summary "$OUT_DIR/scale_target_gap_summary.json" \
  --scale-history-summary "$OUT_DIR/scale_history_summary.json" \
  --out "$OUT_DIR/scale_velocity_forecast_summary.json" \
  --report-out "$OUT_DIR/scale_velocity_forecast_summary.md"

python3 -m gateforge.dataset_family_gap_action_plan_v1 \
  --real-model-family-coverage-board-summary "$OUT_DIR/real_model_family_coverage_board_summary.json" \
  --weekly-scale-milestone-checkpoint-summary "$OUT_DIR/weekly_scale_milestone_checkpoint_summary.json" \
  --out "$OUT_DIR/family_gap_action_plan_summary.json" \
  --report-out "$OUT_DIR/family_gap_action_plan_summary.md"

python3 -m gateforge.dataset_failure_balance_backfill_plan_v1 \
  --mutation-failure-type-balance-guard-summary "$OUT_DIR/mutation_failure_type_balance_guard_summary.json" \
  --out "$OUT_DIR/failure_balance_backfill_plan_summary.json" \
  --report-out "$OUT_DIR/failure_balance_backfill_plan_summary.md"

if [ -f "$ACTION_BACKLOG_HISTORY_LAST_SUMMARY_PATH" ]; then
  cp "$ACTION_BACKLOG_HISTORY_LAST_SUMMARY_PATH" "$OUT_DIR/action_backlog_history_previous_summary.json"
else
  rm -f "$OUT_DIR/action_backlog_history_previous_summary.json"
fi

python3 -m gateforge.dataset_scale_action_backlog_history_v1 \
  --scale-execution-priority-board-summary "$OUT_DIR/scale_execution_priority_board_summary.json" \
  --family-gap-action-plan-summary "$OUT_DIR/family_gap_action_plan_summary.json" \
  --failure-balance-backfill-plan-summary "$OUT_DIR/failure_balance_backfill_plan_summary.json" \
  --weekly-scale-milestone-checkpoint-summary "$OUT_DIR/weekly_scale_milestone_checkpoint_summary.json" \
  --ledger "$ACTION_BACKLOG_HISTORY_LEDGER_PATH" \
  --out "$OUT_DIR/action_backlog_history_summary.json" \
  --report-out "$OUT_DIR/action_backlog_history_summary.md"

if [ -f "$OUT_DIR/action_backlog_history_previous_summary.json" ]; then
  python3 -m gateforge.dataset_scale_action_backlog_trend_v1 \
    --previous "$OUT_DIR/action_backlog_history_previous_summary.json" \
    --current "$OUT_DIR/action_backlog_history_summary.json" \
    --out "$OUT_DIR/action_backlog_history_trend_summary.json" \
    --report-out "$OUT_DIR/action_backlog_history_trend_summary.md"
else
  cat > "$OUT_DIR/action_backlog_history_trend_summary.json" <<'JSON'
{
  "status": "PASS",
  "trend": {
    "status_transition": "BOOTSTRAP->BOOTSTRAP",
    "delta_avg_total_actions": 0.0,
    "delta_avg_total_p0_actions": 0.0,
    "delta_avg_checkpoint_score": 0.0,
    "alerts": []
  },
  "alerts": []
}
JSON
fi
mkdir -p "$(dirname "$ACTION_BACKLOG_HISTORY_LAST_SUMMARY_PATH")"
cp "$OUT_DIR/action_backlog_history_summary.json" "$ACTION_BACKLOG_HISTORY_LAST_SUMMARY_PATH"

python3 -m gateforge.dataset_scale_checkpoint_feedback_gate_v1 \
  --weekly-scale-milestone-checkpoint-summary "$OUT_DIR/weekly_scale_milestone_checkpoint_summary.json" \
  --scale-action-backlog-history-summary "$OUT_DIR/action_backlog_history_summary.json" \
  --scale-action-backlog-trend-summary "$OUT_DIR/action_backlog_history_trend_summary.json" \
  --scale-velocity-forecast-summary "$OUT_DIR/scale_velocity_forecast_summary.json" \
  --out "$OUT_DIR/scale_checkpoint_feedback_gate_summary.json" \
  --report-out "$OUT_DIR/scale_checkpoint_feedback_gate_summary.md"

python3 - <<'PY'
import json
import os
from pathlib import Path

out = Path(os.environ["OUT_DIR"])
summary_path = out / "summary.json"
summary = json.loads(summary_path.read_text(encoding="utf-8"))
history = json.loads((out / "scale_history_summary.json").read_text(encoding="utf-8"))
gap = json.loads((out / "scale_target_gap_summary.json").read_text(encoding="utf-8"))
board = json.loads((out / "scale_execution_priority_board_summary.json").read_text(encoding="utf-8"))
checkpoint = json.loads((out / "weekly_scale_milestone_checkpoint_summary.json").read_text(encoding="utf-8"))
velocity = json.loads((out / "scale_velocity_forecast_summary.json").read_text(encoding="utf-8"))
family_plan = json.loads((out / "family_gap_action_plan_summary.json").read_text(encoding="utf-8"))
failure_plan = json.loads((out / "failure_balance_backfill_plan_summary.json").read_text(encoding="utf-8"))
action_history = json.loads((out / "action_backlog_history_summary.json").read_text(encoding="utf-8"))
action_trend = json.loads((out / "action_backlog_history_trend_summary.json").read_text(encoding="utf-8"))
feedback_gate = json.loads((out / "scale_checkpoint_feedback_gate_summary.json").read_text(encoding="utf-8"))

flags = summary.get("result_flags") if isinstance(summary.get("result_flags"), dict) else {}
flags["scale_history_exists"] = "PASS" if str(history.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL"
flags["scale_target_gap_exists"] = "PASS" if str(gap.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL"
flags["scale_execution_board_exists"] = "PASS" if str(board.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL"
flags["weekly_scale_milestone_checkpoint_exists"] = "PASS" if str(checkpoint.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL"
flags["scale_velocity_forecast_exists"] = "PASS" if str(velocity.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL"
flags["family_gap_action_plan_exists"] = "PASS" if str(family_plan.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL"
flags["failure_balance_backfill_plan_exists"] = "PASS" if str(failure_plan.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL"
flags["action_backlog_history_exists"] = "PASS" if str(action_history.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL"
flags["action_backlog_trend_exists"] = "PASS" if str(action_trend.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL"
flags["checkpoint_feedback_gate_exists"] = "PASS" if str(feedback_gate.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL"

summary["result_flags"] = flags
summary["scale_history_status"] = history.get("status")
summary["scale_history_total_records"] = history.get("total_records")
summary["scale_history_delta_canonical_total_models"] = history.get("delta_canonical_total_models")
summary["scale_target_gap_status"] = gap.get("status")
summary["scale_target_gap_overall_progress_pct"] = gap.get("overall_progress_pct")
summary["scale_target_gap_models"] = gap.get("gap_models")
summary["scale_target_gap_reproducible_mutations"] = gap.get("gap_reproducible_mutations")
summary["scale_target_gap_hardness_score"] = gap.get("gap_hardness_score")
summary["scale_execution_board_status"] = board.get("status")
summary["scale_execution_board_task_count"] = board.get("task_count")
summary["scale_execution_board_p0_tasks"] = board.get("p0_tasks")
summary["scale_execution_board_projected_weeks"] = board.get("projected_weeks_to_close_key_gaps")
summary["weekly_scale_milestone_checkpoint_status"] = checkpoint.get("status")
summary["weekly_scale_milestone_checkpoint_score"] = checkpoint.get("milestone_score")
summary["weekly_scale_milestone_checkpoint_grade"] = checkpoint.get("milestone_grade")
summary["weekly_scale_milestone_checkpoint_top_actions_count"] = checkpoint.get("top_actions_count")
summary["scale_velocity_forecast_status"] = velocity.get("status")
summary["scale_velocity_model_gap_weeks_to_close"] = velocity.get("model_gap_weeks_to_close")
summary["scale_velocity_mutation_gap_weeks_to_close"] = velocity.get("mutation_gap_weeks_to_close")
summary["scale_velocity_on_track_within_horizon"] = velocity.get("on_track_within_horizon")
summary["family_gap_action_plan_status"] = family_plan.get("status")
summary["family_gap_action_plan_total_actions"] = family_plan.get("total_actions")
summary["family_gap_action_plan_p0_actions"] = family_plan.get("p0_actions")
summary["failure_balance_backfill_plan_status"] = failure_plan.get("status")
summary["failure_balance_backfill_plan_total_actions"] = failure_plan.get("total_actions")
summary["failure_balance_backfill_plan_p0_actions"] = failure_plan.get("p0_actions")
summary["action_backlog_history_status"] = action_history.get("status")
summary["action_backlog_history_total_records"] = action_history.get("total_records")
summary["action_backlog_history_latest_total_p0_actions"] = action_history.get("latest_total_p0_actions")
summary["action_backlog_trend_status"] = action_trend.get("status")
summary["action_backlog_trend_delta_avg_total_p0_actions"] = (action_trend.get("trend") or {}).get("delta_avg_total_p0_actions")
summary["checkpoint_feedback_gate_status"] = feedback_gate.get("status")
summary["checkpoint_feedback_gate_feedback_score"] = feedback_gate.get("feedback_score")
summary["checkpoint_feedback_gate_adjusted_status"] = feedback_gate.get("adjusted_checkpoint_status")

summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
md_path = out / "summary.md"
old = md_path.read_text(encoding="utf-8")
extra_lines = [
    f"- scale_history_status: `{summary.get('scale_history_status')}`",
    f"- scale_history_total_records: `{summary.get('scale_history_total_records')}`",
    f"- scale_history_delta_canonical_total_models: `{summary.get('scale_history_delta_canonical_total_models')}`",
    f"- scale_target_gap_status: `{summary.get('scale_target_gap_status')}`",
    f"- scale_target_gap_overall_progress_pct: `{summary.get('scale_target_gap_overall_progress_pct')}`",
    f"- scale_target_gap_models: `{summary.get('scale_target_gap_models')}`",
    f"- scale_target_gap_reproducible_mutations: `{summary.get('scale_target_gap_reproducible_mutations')}`",
    f"- scale_target_gap_hardness_score: `{summary.get('scale_target_gap_hardness_score')}`",
    f"- scale_execution_board_status: `{summary.get('scale_execution_board_status')}`",
    f"- scale_execution_board_task_count: `{summary.get('scale_execution_board_task_count')}`",
    f"- scale_execution_board_p0_tasks: `{summary.get('scale_execution_board_p0_tasks')}`",
    f"- scale_execution_board_projected_weeks: `{summary.get('scale_execution_board_projected_weeks')}`",
    f"- weekly_scale_milestone_checkpoint_status: `{summary.get('weekly_scale_milestone_checkpoint_status')}`",
    f"- weekly_scale_milestone_checkpoint_score: `{summary.get('weekly_scale_milestone_checkpoint_score')}`",
    f"- weekly_scale_milestone_checkpoint_grade: `{summary.get('weekly_scale_milestone_checkpoint_grade')}`",
    f"- weekly_scale_milestone_checkpoint_top_actions_count: `{summary.get('weekly_scale_milestone_checkpoint_top_actions_count')}`",
    f"- scale_velocity_forecast_status: `{summary.get('scale_velocity_forecast_status')}`",
    f"- scale_velocity_model_gap_weeks_to_close: `{summary.get('scale_velocity_model_gap_weeks_to_close')}`",
    f"- scale_velocity_mutation_gap_weeks_to_close: `{summary.get('scale_velocity_mutation_gap_weeks_to_close')}`",
    f"- scale_velocity_on_track_within_horizon: `{summary.get('scale_velocity_on_track_within_horizon')}`",
    f"- family_gap_action_plan_status: `{summary.get('family_gap_action_plan_status')}`",
    f"- family_gap_action_plan_total_actions: `{summary.get('family_gap_action_plan_total_actions')}`",
    f"- family_gap_action_plan_p0_actions: `{summary.get('family_gap_action_plan_p0_actions')}`",
    f"- failure_balance_backfill_plan_status: `{summary.get('failure_balance_backfill_plan_status')}`",
    f"- failure_balance_backfill_plan_total_actions: `{summary.get('failure_balance_backfill_plan_total_actions')}`",
    f"- failure_balance_backfill_plan_p0_actions: `{summary.get('failure_balance_backfill_plan_p0_actions')}`",
    f"- action_backlog_history_status: `{summary.get('action_backlog_history_status')}`",
    f"- action_backlog_history_total_records: `{summary.get('action_backlog_history_total_records')}`",
    f"- action_backlog_history_latest_total_p0_actions: `{summary.get('action_backlog_history_latest_total_p0_actions')}`",
    f"- action_backlog_trend_status: `{summary.get('action_backlog_trend_status')}`",
    f"- action_backlog_trend_delta_avg_total_p0_actions: `{summary.get('action_backlog_trend_delta_avg_total_p0_actions')}`",
    f"- checkpoint_feedback_gate_status: `{summary.get('checkpoint_feedback_gate_status')}`",
    f"- checkpoint_feedback_gate_feedback_score: `{summary.get('checkpoint_feedback_gate_feedback_score')}`",
    f"- checkpoint_feedback_gate_adjusted_status: `{summary.get('checkpoint_feedback_gate_adjusted_status')}`",
]
md_path.write_text(old + "\n" + "\n".join(extra_lines) + "\n", encoding="utf-8")
print(json.dumps({"bundle_status": summary.get("bundle_status"), "scale_target_gap_status": summary.get("scale_target_gap_status")}))
if str(summary.get("bundle_status") or "") != "PASS":
    raise SystemExit(1)
PY

cat "$OUT_DIR/summary.json"
