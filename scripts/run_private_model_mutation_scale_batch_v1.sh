#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_PRIVATE_BATCH_OUT_DIR:-artifacts/private_model_mutation_scale_batch_v1}"
mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/*.json "$OUT_DIR"/*.md "$OUT_DIR"/*.jsonl
export OUT_DIR

ROOTS_RAW="${GATEFORGE_PRIVATE_MODEL_ROOTS:-assets_private/modelica:examples_private/modelica:data/private_modelica}"
ROOTS_CSV="${ROOTS_RAW//:/,}"
IFS=',' read -r -a ROOTS <<< "$ROOTS_CSV"

DISCOVERY_ARGS=()
for r in "${ROOTS[@]}"; do
  rr="$(echo "$r" | xargs)"
  if [ -n "$rr" ]; then
    DISCOVERY_ARGS+=(--model-root "$rr")
  fi
done

python3 -m gateforge.dataset_real_model_asset_discovery_v1 \
  "${DISCOVERY_ARGS[@]}" \
  --source-name "private_modelica_asset_pool" \
  --source-domain "physical_ai" \
  --source-url-prefix "local://" \
  --source-repo "private" \
  --source-commit "workspace" \
  --license-tag "Apache-2.0" \
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

python3 -m gateforge.dataset_mutation_bulk_pack_builder_v1 \
  --model-registry "$OUT_DIR/intake_registry_rows.json" \
  --target-scales "medium,large" \
  --failure-types "simulate_error,model_check_error,semantic_regression,numerical_instability,constraint_violation" \
  --mutations-per-failure-type "${GATEFORGE_MUTATIONS_PER_FAILURE_TYPE:-2}" \
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

flags = {
    "discovery_exists": "PASS" if int(discovery.get("total_candidates", 0)) >= 0 else "FAIL",
    "pipeline_exists": "PASS" if int(pipeline.get("total_candidates", 0)) >= 0 else "FAIL",
    "runner_exists": "PASS" if int(runner.get("total_candidates", 0)) >= 0 else "FAIL",
    "pack_exists": "PASS" if int(pack.get("total_mutations", 0)) >= 0 else "FAIL",
    "realrun_exists": "PASS" if int(realrun.get("total_mutations", 0)) >= 0 else "FAIL",
    "gate_status_present": "PASS" if str(gate.get("status") or "") in {"PASS", "NEEDS_REVIEW", "FAIL"} else "FAIL",
}
bundle_status = "PASS" if all(v == "PASS" for v in flags.values()) else "FAIL"

summary = {
    "bundle_status": bundle_status,
    "scale_gate_status": gate.get("status"),
    "discovered_models": discovery.get("total_candidates"),
    "accepted_models": runner.get("accepted_count"),
    "accepted_large_models": runner.get("accepted_large_count"),
    "generated_mutations": pack.get("total_mutations"),
    "reproducible_mutations": realrun.get("executed_count"),
    "result_flags": flags,
}

(out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
(out / "summary.md").write_text(
    "\n".join(
        [
            "# GateForge Private Model + Mutation Scale Batch v1",
            "",
            f"- bundle_status: `{summary['bundle_status']}`",
            f"- scale_gate_status: `{summary['scale_gate_status']}`",
            f"- discovered_models: `{summary['discovered_models']}`",
            f"- accepted_models: `{summary['accepted_models']}`",
            f"- accepted_large_models: `{summary['accepted_large_models']}`",
            f"- generated_mutations: `{summary['generated_mutations']}`",
            f"- reproducible_mutations: `{summary['reproducible_mutations']}`",
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
