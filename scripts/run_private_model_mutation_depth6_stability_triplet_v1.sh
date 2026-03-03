#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${GATEFORGE_DEPTH6_STABILITY_OUT_DIR:-artifacts/private_model_mutation_depth6_stability_triplet_v1}"
WINDOW_SIZE="${GATEFORGE_STABILITY_WINDOW_SIZE:-3}"
INCLUDE_EXISTING="${GATEFORGE_STABILITY_INCLUDE_EXISTING:-1}"
EXISTING_SCALE_SUMMARY="${GATEFORGE_EXISTING_DEPTH6_SCALE_SUMMARY:-artifacts/private_model_mutation_scale_depth6_sprint_v1/summary.json}"

mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR"/summary.json "$OUT_DIR"/summary.md

RECORD_SCALE=()
RECORD_UNIQ=()

if [ "$INCLUDE_EXISTING" = "1" ] && [ -f "$EXISTING_SCALE_SUMMARY" ]; then
  EXISTING_DIR="$(cd "$(dirname "$EXISTING_SCALE_SUMMARY")" && pwd)"
  EXISTING_UNIQ="$OUT_DIR/existing_uniqueness_summary.json"
  python3 -m gateforge.dataset_real_model_uniqueness_guard_v1 \
    --intake-runner-accepted "$EXISTING_DIR/intake_runner_accepted.json" \
    --intake-registry-rows "$EXISTING_DIR/intake_registry_rows.json" \
    --out "$EXISTING_UNIQ" \
    --report-out "$OUT_DIR/existing_uniqueness_summary.md"
  RECORD_SCALE+=("$EXISTING_SCALE_SUMMARY")
  RECORD_UNIQ+=("$EXISTING_UNIQ")
fi

existing_count="${#RECORD_SCALE[@]}"
remaining=$((WINDOW_SIZE - existing_count))
if [ "$remaining" -lt 0 ]; then
  remaining=0
fi

for ((i=1; i<=remaining; i++)); do
  run_index=$((existing_count + i))
  run_dir="$OUT_DIR/run_${run_index}"
  mkdir -p "$run_dir"
  GATEFORGE_PRIVATE_BATCH_OUT_DIR="$run_dir" \
  bash scripts/run_private_model_mutation_depth6_sprint_v1.sh

  uniq_path="$run_dir/uniqueness_summary.json"
  python3 -m gateforge.dataset_real_model_uniqueness_guard_v1 \
    --intake-runner-accepted "$run_dir/intake_runner_accepted.json" \
    --intake-registry-rows "$run_dir/intake_registry_rows.json" \
    --out "$uniq_path" \
    --report-out "$run_dir/uniqueness_summary.md"

  RECORD_SCALE+=("$run_dir/summary.json")
  RECORD_UNIQ+=("$uniq_path")
done

CMD=(python3 -m gateforge.dataset_real_model_mutation_stability_triplet_v1
  --ledger "$OUT_DIR/history.jsonl"
  --window-size "$WINDOW_SIZE"
  --out "$OUT_DIR/summary.json"
  --report-out "$OUT_DIR/summary.md"
)

for p in "${RECORD_SCALE[@]}"; do
  CMD+=(--record-scale-summary "$p")
done
for p in "${RECORD_UNIQ[@]}"; do
  CMD+=(--record-uniqueness-summary "$p")
done

"${CMD[@]}"

cat "$OUT_DIR/summary.json"
